"""
Batch (production execution) service — 14a: create, list, get, WIP.

WIP is derived from the immutable ledgers, never stored:
    waiting(batch, stage) = moved_in - moved_out - rejected
Creating a batch records an intake movement (from_stage NULL -> first stage); all units start
there waiting. Advance/consume (14b) and rejects (14c) extend this.
"""

from typing import Dict, List, Optional
from decimal import Decimal
from datetime import datetime

from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session

from app.core.db.engine import run_db
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.pagination import paginate_multi, build_paginated_response
from app.core.utils import search_words, normalize_unicode
from app.modules.products.models import Product
from app.modules.stages.models import Stage
from .models import Batch, BatchMovement, BatchReject, BATCH_OPEN

ZERO = Decimal("0")


# ----------------------------- WIP derivation -----------------------------

def _active_stages(db: Session) -> List[Stage]:
    return list(db.execute(
        select(Stage).where(Stage.deleted_at.is_(None)).order_by(Stage.sequence)
    ).scalars().all())


def _wip_by_stage(db: Session, batch_id: int) -> Dict[int, Decimal]:
    """{stage_id: waiting} for one batch, from the ledgers."""
    moved_in = dict(db.execute(
        select(BatchMovement.to_stage_id, func.sum(BatchMovement.quantity))
        .where(BatchMovement.batch_id == batch_id, BatchMovement.deleted_at.is_(None))
        .group_by(BatchMovement.to_stage_id)
    ).all())
    moved_out = dict(db.execute(
        select(BatchMovement.from_stage_id, func.sum(BatchMovement.quantity))
        .where(BatchMovement.batch_id == batch_id, BatchMovement.deleted_at.is_(None),
               BatchMovement.from_stage_id.isnot(None))
        .group_by(BatchMovement.from_stage_id)
    ).all())
    rejected = dict(db.execute(
        select(BatchReject.stage_id, func.sum(BatchReject.quantity))
        .where(BatchReject.batch_id == batch_id, BatchReject.deleted_at.is_(None))
        .group_by(BatchReject.stage_id)
    ).all())
    stage_ids = set(moved_in) | set(moved_out) | set(rejected)
    return {
        sid: (moved_in.get(sid) or ZERO) - (moved_out.get(sid) or ZERO) - (rejected.get(sid) or ZERO)
        for sid in stage_ids
    }


def _current_stage(wip: Dict[int, Decimal], stages: List[Stage]) -> Optional[Stage]:
    """Highest-sequence stage with waiting > 0 (where the units currently sit)."""
    for s in sorted(stages, key=lambda x: x.sequence, reverse=True):
        if (wip.get(s.id) or ZERO) > 0:
            return s
    return None


def _bulk_current_stage(
    db: Session, batch_ids: List[int], stages: List[Stage]
) -> Dict[int, Optional[Stage]]:
    """{batch_id: current Stage or None} for a page of batches, in 3 grouped queries."""
    if not batch_ids:
        return {}

    waiting: Dict[int, Dict[int, Decimal]] = {bid: {} for bid in batch_ids}

    def grouped(col, table, extra=None):
        q = (
            select(table.batch_id, col, func.sum(table.quantity))
            .where(table.batch_id.in_(batch_ids), table.deleted_at.is_(None))
        )
        if extra is not None:
            q = q.where(extra)
        return db.execute(q.group_by(table.batch_id, col)).all()

    for bid, sid, qty in grouped(BatchMovement.to_stage_id, BatchMovement):
        waiting[bid][sid] = waiting[bid].get(sid, ZERO) + (qty or ZERO)
    for bid, sid, qty in grouped(BatchMovement.from_stage_id, BatchMovement,
                                 BatchMovement.from_stage_id.isnot(None)):
        waiting[bid][sid] = waiting[bid].get(sid, ZERO) - (qty or ZERO)
    for bid, sid, qty in grouped(BatchReject.stage_id, BatchReject):
        waiting[bid][sid] = waiting[bid].get(sid, ZERO) - (qty or ZERO)

    out: Dict[int, Optional[Stage]] = {}
    for bid in batch_ids:
        cur = None
        for s in sorted(stages, key=lambda x: x.sequence, reverse=True):
            if waiting[bid].get(s.id, ZERO) > 0:
                cur = s
                break
        out[bid] = cur
    return out


# ----------------------------- response shaping -----------------------------

class _ProductLite:
    """Tiny adapter so _to_response can read part_no/name uniformly."""
    def __init__(self, part_no, name):
        self.part_no, self.name = part_no, name


def _to_response(batch: Batch, product, current: Optional[Stage]):
    from .schemas import BatchResponse
    return BatchResponse(
        id=batch.id,
        batch_no=batch.batch_no,
        product_id=batch.product_id,
        product_part_no=product.part_no if product else None,
        product_name=product.name if product else None,
        style=batch.style,
        colour=batch.colour,
        quantity=batch.quantity,
        status=batch.status,
        current_stage_id=current.id if current else None,
        current_stage_name=current.name if current else None,
        created_by=batch.created_by,
        created_at=batch.created_at,
        updated_at=batch.updated_at,
        deleted_at=batch.deleted_at,
    )


def _detail(db: Session, batch: Batch, product, stages: List[Stage]):
    """Build a BatchDetailResponse (batch + full per-stage WIP)."""
    from .schemas import BatchDetailResponse, BatchWipLine

    wip = _wip_by_stage(db, batch.id)
    cur = _current_stage(wip, stages)
    base = _to_response(batch, product, cur)
    lines = [
        BatchWipLine(stage_id=s.id, stage_name=s.name, sequence=s.sequence,
                     waiting=(wip.get(s.id) or ZERO))
        for s in stages
    ]
    return BatchDetailResponse(**base.model_dump(), wip=lines)


# ----------------------------- helpers -----------------------------

def _require_product(db: Session, product_id: int) -> Product:
    product = db.execute(
        select(Product).where(Product.id == product_id, Product.deleted_at.is_(None))
    ).scalar_one_or_none()
    if not product:
        raise ValidationError(f"Product {product_id} does not exist")
    return product


def _next_batch_no(db: Session) -> str:
    rows = db.execute(
        select(Batch.batch_no).where(Batch.batch_no.like("B-%"))
    ).scalars().all()
    max_n = 0
    for bn in rows:
        suffix = bn.rsplit("-", 1)[-1]
        if suffix.isdigit():
            max_n = max(max_n, int(suffix))
    return f"B-{max_n + 1:04d}"


class BatchService:
    @staticmethod
    async def create(dto, user_id: Optional[int] = None):
        def _create(db: Session):
            product = _require_product(db, dto.product_id)

            stages = _active_stages(db)
            if not stages:
                raise ValidationError("No stages configured")
            if dto.start_stage_id is not None:
                start = next((s for s in stages if s.id == dto.start_stage_id), None)
                if start is None:
                    raise ValidationError(f"Stage {dto.start_stage_id} does not exist")
            else:
                start = stages[0]  # lowest sequence

            batch_no = dto.batch_no.strip() if dto.batch_no else _next_batch_no(db)
            clash = db.execute(
                select(Batch.id).where(Batch.batch_no == batch_no, Batch.deleted_at.is_(None))
            ).first()
            if clash:
                raise ConflictError(f"Batch {batch_no} already exists")

            now = datetime.utcnow()
            batch = Batch(
                batch_no=batch_no,
                product_id=dto.product_id,
                style=normalize_unicode(dto.style) if dto.style else dto.style,
                colour=normalize_unicode(dto.colour) if dto.colour else dto.colour,
                quantity=dto.quantity,
                status=BATCH_OPEN,
                created_by=user_id,
                created_at=now,
                updated_at=now,
            )
            db.add(batch)
            db.flush()

            # Intake: all units enter the flow at the first stage (from_stage NULL).
            db.add(BatchMovement(
                batch_id=batch.id,
                from_stage_id=None,
                to_stage_id=start.id,
                quantity=dto.quantity,
                moved_by=user_id,
                created_at=now,
                updated_at=now,
            ))
            db.flush()

            return _detail(db, batch, product, stages)

        return await run_db(_create)

    @staticmethod
    async def find_all_paginated(
        page: int = 1,
        page_size: int = 25,
        search: Optional[str] = None,
        product_id: Optional[int] = None,
        status: Optional[str] = None,
    ) -> dict:
        words = search_words(search)

        def _find(db: Session) -> dict:
            query = (
                select(Batch, Product.part_no, Product.name)
                .join(Product, Batch.product_id == Product.id)
                .where(Batch.deleted_at.is_(None))
            )
            if product_id is not None:
                query = query.where(Batch.product_id == product_id)
            if status is not None:
                query = query.where(Batch.status == status)
            for word in words:
                pattern = f"%{word}%"
                query = query.where(or_(
                    Batch.batch_no.ilike(pattern),
                    Batch.style.ilike(pattern),
                    Batch.colour.ilike(pattern),
                    Product.part_no.ilike(pattern),
                    Product.name.ilike(pattern),
                ))
            query = query.order_by(Batch.created_at.desc(), Batch.id.desc())

            rows, total = paginate_multi(db, query, page, page_size)
            stages = _active_stages(db)
            batch_ids = [b.id for (b, _pn, _nm) in rows]
            current = _bulk_current_stage(db, batch_ids, stages)

            items = [
                _to_response(b, _ProductLite(pn, nm), current.get(b.id))
                for (b, pn, nm) in rows
            ]
            return build_paginated_response(items, total, page, page_size)

        return await run_db(_find)

    @staticmethod
    async def find_one(batch_id: int):
        def _find(db: Session):
            batch = db.execute(
                select(Batch).where(Batch.id == batch_id, Batch.deleted_at.is_(None))
            ).scalar_one_or_none()
            if not batch:
                raise NotFoundError("Batch", batch_id)
            product = db.execute(
                select(Product).where(Product.id == batch.product_id)
            ).scalar_one_or_none()
            return _detail(db, batch, product, _active_stages(db))

        return await run_db(_find)

    @staticmethod
    async def update(batch_id: int, dto):
        def _update(db: Session):
            batch = db.execute(
                select(Batch).where(Batch.id == batch_id, Batch.deleted_at.is_(None))
            ).scalar_one_or_none()
            if not batch:
                raise NotFoundError("Batch", batch_id)
            data = dto.model_dump(exclude_unset=True)
            for k, v in data.items():
                if k in ("style", "colour") and isinstance(v, str):
                    v = normalize_unicode(v) or v
                setattr(batch, k, v)
            batch.updated_at = datetime.utcnow()
            db.flush()
            product = db.execute(
                select(Product).where(Product.id == batch.product_id)
            ).scalar_one_or_none()
            return _detail(db, batch, product, _active_stages(db))

        return await run_db(_update)

    @staticmethod
    async def remove(batch_id: int) -> None:
        def _remove(db: Session) -> None:
            batch = db.execute(
                select(Batch).where(Batch.id == batch_id)
            ).scalar_one_or_none()
            if not batch:
                raise NotFoundError("Batch", batch_id)
            batch.deleted_at = datetime.utcnow()
            db.flush()

        await run_db(_remove)
