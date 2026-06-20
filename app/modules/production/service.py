"""
Batch (production execution) service — 14a: create, list, get, WIP.

WIP is derived from the immutable ledgers, never stored:
    waiting(batch, stage) = moved_in - moved_out - rejected
Creating a batch records an intake movement (from_stage NULL -> first stage); all units start
there waiting. Advance/consume (14b) and rejects (14c) extend this.
"""

from typing import Dict, List, Optional
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime

from sqlalchemy import select, func, or_    
from sqlalchemy.orm import Session, aliased

from app.core.db.engine import run_db
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.pagination import paginate_multi, build_paginated_response
from app.core.utils import search_words, normalize_unicode
from app.modules.products.models import Product
from app.modules.stages.models import Stage
from app.modules.bom.models import BOMLine
from app.modules.raw_materials.models import RawMaterial
from app.modules.operations.models import Operation
from .models import (
    Batch, BatchMovement, BatchReject, MaterialConsumption,
    BATCH_OPEN, BATCH_IN_PROGRESS,
)
from .schemas import (
    BatchCreateDto, BatchAdvanceDto, BatchRejectDto, BatchUpdateDto,
    BatchResponse, BatchDetailResponse, BatchWipLine, ConsumptionLine,
    BatchHistoryResponse, MovementHistoryLine, ConsumptionHistoryLine, RejectHistoryLine,
    MaterialPreviewResponse, MaterialPreviewLine,
)

ZERO = Decimal("0")
_CENTS = Decimal("0.01")


def _q(d: Decimal) -> Decimal:
    """Round to 2dp to match the Numeric(15,2) columns (so response == stored value)."""
    return d.quantize(_CENTS, rounding=ROUND_HALF_UP)


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


def _bulk_wip(db: Session, batch_ids: List[int]) -> Dict[int, Dict[int, Decimal]]:
    """{batch_id: {stage_id: waiting}} for a page of batches, in 3 grouped queries."""
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
    return waiting


# ----------------------------- response shaping -----------------------------

class _ProductLite:
    """Tiny adapter so _to_response can read part_no/name uniformly."""
    def __init__(self, part_no, name):
        self.part_no, self.name = part_no, name


def _to_response(batch: Batch, product, current: Optional[Stage]):
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


def _detail(db: Session, batch: Batch, product, stages: List[Stage],
            consumption=None, warnings=None, wip: Optional[Dict[int, Decimal]] = None):
    """Build a BatchDetailResponse (batch + full per-stage WIP, + any move's consumption).

    `wip` may be passed pre-computed by a caller that already knows the post-write state
    (e.g. advance applies the move's delta in memory) to avoid re-deriving it from the
    ledger. When omitted, it's derived fresh — the two are equal by the ledger's definition
    (waiting = moved_in - moved_out - rejected)."""
    if wip is None:
        wip = _wip_by_stage(db, batch.id)
    cur = _current_stage(wip, stages)
    base = _to_response(batch, product, cur)
    lines = [
        BatchWipLine(stage_id=s.id, stage_name=s.name, sequence=s.sequence,
                     waiting=(wip.get(s.id) or ZERO))
        for s in stages
    ]
    return BatchDetailResponse(
        **base.model_dump(), wip=lines,
        consumption=consumption or [], warnings=warnings or [],
    )


# ----------------------------- consume engine -----------------------------

def _per_unit(line: BOMLine) -> Decimal:
    return (line.qty_per_batch / line.batch_size) if line.batch_size else ZERO


def _stage_bom_rows(db: Session, product_id: int, stage_id: int, colour: Optional[str]):
    """BOM lines (+ material name/unit) for a product at a stage, matched to the batch's
    variant. Match is COLOUR-based (style==colour in the source data, so style is ignored):
    lines whose colour == the batch colour OR is NULL (colour-agnostic materials)."""
    q = (
        select(BOMLine, RawMaterial.name, RawMaterial.unit_type)
        .join(RawMaterial, BOMLine.raw_material_id == RawMaterial.id)
        .where(
            BOMLine.product_id == product_id,
            BOMLine.stage_id == stage_id,
            BOMLine.deleted_at.is_(None),
            RawMaterial.deleted_at.is_(None),
        )
    )
    if colour:
        q = q.where(or_(BOMLine.colour == colour, BOMLine.colour.is_(None)))
    else:
        q = q.where(BOMLine.colour.is_(None))
    return db.execute(q).all()


def _aggregate_materials(rows):
    """Sum per-unit across same-material lines (sum-don't-dedup). -> {rm_id: [per_unit, name, unit]}."""
    agg: Dict[int, list] = {}
    for line, name, unit in rows:
        pu = _per_unit(line)
        if line.raw_material_id in agg:
            agg[line.raw_material_id][0] += pu
        else:
            agg[line.raw_material_id] = [pu, name, unit]
    return agg


def _consume_stage(db: Session, batch: Batch, stage: Stage, qty: Decimal):
    """Consume `stage`'s BOM for `qty` units of `batch`: one material_consumption row per
    material (lines summed), decrement stock, warn-and-allow on negative. Returns
    (consumption_lines, warnings)."""
    agg = _aggregate_materials(_stage_bom_rows(db, batch.product_id, stage.id, batch.colour))
    consumption, warnings = [], []
    now = datetime.utcnow()
    # One round-trip for all materials' stock instead of one db.get per material (N+1).
    # These are the same identity-mapped instances db.get would return, so mutating
    # rm.stock_qty still emits the same UPDATE on flush.
    by_id = {
        rm.id: rm
        for rm in db.execute(
            select(RawMaterial).where(RawMaterial.id.in_(agg.keys()))
        ).scalars().all()
    } if agg else {}
    for rm_id, (per_unit, name, unit) in agg.items():
        need = _q(per_unit * qty)
        rm = by_id.get(rm_id)
        prev = (rm.stock_qty if rm and rm.stock_qty is not None else ZERO)
        new = prev - need
        short = new < 0
        if rm is not None:
            rm.stock_qty = new
        db.add(MaterialConsumption(
            batch_id=batch.id, stage_id=stage.id, raw_material_id=rm_id,
            qty_consumed=need, previous_qty=prev, new_qty=new,
            created_at=now, updated_at=now,
        ))
        consumption.append(ConsumptionLine(
            raw_material_id=rm_id, raw_material_name=name, unit_type=unit,
            qty_consumed=need, previous_stock=prev, new_stock=new, short=short,
        ))
        if short:
            warnings.append(f"{name}: stock now {new} {unit} (short by {abs(new)})")
    db.flush()
    return consumption, warnings


def _next_recipe_stage(db: Session, product_id: int, from_stage: Stage,
                       stages: List[Stage]) -> Optional[Stage]:
    """Next stage by sequence after `from_stage` that the product has a recipe (BOM or ops)
    for — so products that skip stitching advance straight to finishing. Falls back to the
    plain next stage if none later has a recipe."""
    later = sorted((s for s in stages if s.sequence > from_stage.sequence),
                   key=lambda s: s.sequence)
    if not later:
        return None
    recipe_ids = set()
    recipe_ids |= {sid for (sid,) in db.execute(
        select(BOMLine.stage_id).where(
            BOMLine.product_id == product_id, BOMLine.deleted_at.is_(None),
            BOMLine.stage_id.isnot(None)
        ).distinct()
    ).all()}
    recipe_ids |= {sid for (sid,) in db.execute(
        select(Operation.stage_id).where(
            Operation.product_id == product_id, Operation.deleted_at.is_(None),
            Operation.stage_id.isnot(None)
        ).distinct()
    ).all()}
    for s in later:
        if s.id in recipe_ids:
            return s
    return later[0]


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
    async def create(dto: BatchCreateDto, user_id: Optional[int] = None):
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

            # Consume the first stage's BOM on intake (warn-and-allow on negative stock).
            consumption, warnings = _consume_stage(db, batch, start, dto.quantity)
            return _detail(db, batch, product, stages, consumption, warnings)

        return await run_db(_create)

    @staticmethod
    async def advance(batch_id: int, dto: BatchAdvanceDto, user_id: Optional[int] = None):
        def _advance(db: Session):
            batch = db.execute(
                select(Batch).where(Batch.id == batch_id, Batch.deleted_at.is_(None))
            ).scalar_one_or_none()
            if not batch:
                raise NotFoundError("Batch", batch_id)

            stages = _active_stages(db)
            by_id = {s.id: s for s in stages}
            wip = _wip_by_stage(db, batch.id)

            # from stage: explicit or the current stage (where units wait).
            if dto.from_stage_id is not None:
                from_stage = by_id.get(dto.from_stage_id)
                if from_stage is None:
                    raise ValidationError(f"Stage {dto.from_stage_id} does not exist")
            else:
                from_stage = _current_stage(wip, stages)
                if from_stage is None:
                    raise ValidationError("Batch has no units waiting to advance")

            available = wip.get(from_stage.id) or ZERO
            if dto.quantity > available:
                raise ValidationError(
                    f"Only {available} units waiting at {from_stage.name}, cannot move {dto.quantity}"
                )

            # to stage: explicit or the next recipe stage.
            if dto.to_stage_id is not None:
                to_stage = by_id.get(dto.to_stage_id)
                if to_stage is None:
                    raise ValidationError(f"Stage {dto.to_stage_id} does not exist")
                if to_stage.id == from_stage.id:
                    raise ValidationError("to_stage must differ from from_stage")
            else:
                to_stage = _next_recipe_stage(db, batch.product_id, from_stage, stages)
                if to_stage is None:
                    raise ValidationError(f"{from_stage.name} is the last stage; nothing to advance to")

            now = datetime.utcnow()
            db.add(BatchMovement(
                batch_id=batch.id,
                from_stage_id=from_stage.id,
                to_stage_id=to_stage.id,
                quantity=dto.quantity,
                moved_by=user_id,
                created_at=now,
                updated_at=now,
            ))
            db.flush()

            # Consume the TARGET stage's BOM on the move in.
            consumption, warnings = _consume_stage(db, batch, to_stage, dto.quantity)

            if batch.status == BATCH_OPEN:
                batch.status = BATCH_IN_PROGRESS
            batch.updated_at = now
            db.flush()

            product = db.execute(
                select(Product).where(Product.id == batch.product_id)
            ).scalar_one_or_none()

            # Post-move WIP = pre-move WIP + this one movement's effect. By the ledger
            # definition (waiting = moved_in - moved_out - rejected), inserting a single
            # (from -> to, qty) movement shifts exactly: -qty at `from`, +qty at `to`,
            # everything else unchanged (consume touches stock, not unit WIP). So we apply
            # the delta in memory instead of re-deriving WIP from the ledger (saves 3 trips).
            # INVARIANT: advance writes exactly one movement and no rejects — if that ever
            # changes, update this delta or pass wip=None to fall back to re-derivation.
            wip_after = dict(wip)
            wip_after[from_stage.id] = (wip_after.get(from_stage.id) or ZERO) - dto.quantity
            wip_after[to_stage.id] = (wip_after.get(to_stage.id) or ZERO) + dto.quantity
            return _detail(db, batch, product, stages, consumption, warnings, wip=wip_after)

        return await run_db(_advance)

    @staticmethod
    async def reject(batch_id: int, dto: BatchRejectDto, user_id: Optional[int] = None):
        def _reject(db: Session):
            batch = db.execute(
                select(Batch).where(Batch.id == batch_id, Batch.deleted_at.is_(None))
            ).scalar_one_or_none()
            if not batch:
                raise NotFoundError("Batch", batch_id)

            stages = _active_stages(db)
            by_id = {s.id: s for s in stages}
            wip = _wip_by_stage(db, batch.id)

            if dto.stage_id is not None:
                stage = by_id.get(dto.stage_id)
                if stage is None:
                    raise ValidationError(f"Stage {dto.stage_id} does not exist")
            else:
                stage = _current_stage(wip, stages)
                if stage is None:
                    raise ValidationError("Batch has no units to reject")

            available = wip.get(stage.id) or ZERO
            if dto.quantity > available:
                raise ValidationError(
                    f"Only {available} units waiting at {stage.name}, cannot reject {dto.quantity}"
                )

            now = datetime.utcnow()
            db.add(BatchReject(
                batch_id=batch.id,
                stage_id=stage.id,
                quantity=dto.quantity,
                reason=normalize_unicode(dto.reason) if dto.reason else dto.reason,
                created_by=user_id,
                created_at=now,
                updated_at=now,
            ))
            batch.updated_at = now
            db.flush()

            product = db.execute(
                select(Product).where(Product.id == batch.product_id)
            ).scalar_one_or_none()
            return _detail(db, batch, product, stages)

        return await run_db(_reject)

    @staticmethod
    async def history(batch_id: int):
        def _hist(db: Session) -> BatchHistoryResponse:
            if not db.execute(
                select(Batch.id).where(Batch.id == batch_id, Batch.deleted_at.is_(None))
            ).first():
                raise NotFoundError("Batch", batch_id)

            FromStage, ToStage = aliased(Stage), aliased(Stage)
            mv = db.execute(
                select(BatchMovement, FromStage.name, ToStage.name)
                .outerjoin(FromStage, BatchMovement.from_stage_id == FromStage.id)
                .outerjoin(ToStage, BatchMovement.to_stage_id == ToStage.id)
                .where(BatchMovement.batch_id == batch_id, BatchMovement.deleted_at.is_(None))
                .order_by(BatchMovement.moved_at, BatchMovement.id)
            ).all()
            movements = [
                MovementHistoryLine(from_stage_name=fn, to_stage_name=tn, quantity=m.quantity, moved_at=m.moved_at)
                for (m, fn, tn) in mv
            ]

            cons = db.execute(
                select(MaterialConsumption, Stage.name, RawMaterial.name)
                .outerjoin(Stage, MaterialConsumption.stage_id == Stage.id)
                .join(RawMaterial, MaterialConsumption.raw_material_id == RawMaterial.id)
                .where(MaterialConsumption.batch_id == batch_id, MaterialConsumption.deleted_at.is_(None))
                .order_by(MaterialConsumption.created_at, MaterialConsumption.id)
            ).all()
            consumption = [
                ConsumptionHistoryLine(stage_name=sn, raw_material_name=rn, qty_consumed=c.qty_consumed,
                                       new_qty=c.new_qty, created_at=c.created_at)
                for (c, sn, rn) in cons
            ]

            rj = db.execute(
                select(BatchReject, Stage.name)
                .outerjoin(Stage, BatchReject.stage_id == Stage.id)
                .where(BatchReject.batch_id == batch_id, BatchReject.deleted_at.is_(None))
                .order_by(BatchReject.created_at, BatchReject.id)
            ).all()
            rejects = [
                RejectHistoryLine(stage_name=sn, quantity=r.quantity, reason=r.reason, created_at=r.created_at)
                for (r, sn) in rj
            ]
            return BatchHistoryResponse(movements=movements, consumption=consumption, rejects=rejects)

        return await run_db(_hist)

    @staticmethod
    async def material_preview(batch_id: int, stage_id: int, quantity: Decimal):

        def _preview(db: Session) -> MaterialPreviewResponse:
            batch = db.execute(
                select(Batch).where(Batch.id == batch_id, Batch.deleted_at.is_(None))
            ).scalar_one_or_none()
            if not batch:
                raise NotFoundError("Batch", batch_id)
            stage = db.execute(
                select(Stage).where(Stage.id == stage_id, Stage.deleted_at.is_(None))
            ).scalar_one_or_none()
            if not stage:
                raise ValidationError(f"Stage {stage_id} does not exist")

            agg = _aggregate_materials(_stage_bom_rows(db, batch.product_id, stage.id, batch.colour))
            # One round-trip for all materials instead of one db.get per material (N+1).
            # This preview fires on every keystroke in the move dialog, so the per-material
            # round-trips were the hottest avoidable cost on the read path. Same objects
            # db.get would return; stock read verbatim (preserves the stored 0.00 scale).
            by_id = {
                rm.id: rm
                for rm in db.execute(
                    select(RawMaterial).where(RawMaterial.id.in_(agg.keys()))
                ).scalars().all()
            } if agg else {}
            lines = []
            for rm_id, (per_unit, name, unit) in agg.items():
                need = _q(per_unit * quantity)
                rm = by_id.get(rm_id)
                stock = (rm.stock_qty if rm and rm.stock_qty is not None else ZERO)
                shortage = max(ZERO, need - stock)
                lines.append(MaterialPreviewLine(
                    raw_material_id=rm_id, raw_material_name=name, unit_type=unit,
                    needed_qty=need, current_stock=stock, shortage=shortage,
                    status=("ok" if shortage == 0 else "low"),
                ))
            return MaterialPreviewResponse(
                batch_id=batch.id, stage_id=stage.id, stage_name=stage.name,
                quantity=quantity, materials=lines,
            )

        return await run_db(_preview)

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
            ordered = sorted(stages, key=lambda s: s.sequence, reverse=True)
            batch_ids = [b.id for (b, _pn, _nm) in rows]
            wip_map = _bulk_wip(db, batch_ids)

            items = []
            for (b, pn, nm) in rows:
                w = wip_map.get(b.id, {})
                current = next((s for s in ordered if (w.get(s.id) or ZERO) > 0), None)
                resp = _to_response(b, _ProductLite(pn, nm), current)
                # Per-stage split (non-zero stages only) so the board can show a batch in
                # every stage it has units, not just the furthest one.
                resp.wip = [
                    BatchWipLine(stage_id=s.id, stage_name=s.name, sequence=s.sequence,
                                 waiting=(w.get(s.id) or ZERO))
                    for s in stages if (w.get(s.id) or ZERO) != 0
                ]
                items.append(resp)
            return build_paginated_response(items, total, page, page_size)

        return await run_db(_find)

    @staticmethod
    async def find_one(batch_id: int):
        def _find(db: Session):
            # Batch + product in one JOIN (matches the board list) instead of two selects.
            row = db.execute(
                select(Batch, Product.part_no, Product.name)
                .join(Product, Batch.product_id == Product.id)
                .where(Batch.id == batch_id, Batch.deleted_at.is_(None))
            ).first()
            if not row:
                raise NotFoundError("Batch", batch_id)
            batch, part_no, name = row
            return _detail(db, batch, _ProductLite(part_no, name), _active_stages(db))

        return await run_db(_find)

    @staticmethod
    async def update(batch_id: int, dto: BatchUpdateDto):
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
