"""
Work log service (new schema). Piece-rate labor anchored on operations.

- rate defaults to the operation's rate (overridable); rate + total_amount are SNAPSHOTTED
  so later operation rate changes never rewrite history. Pay = quantity * rate.
- bulk_create: one worker, many entries (the worklog grid) in a single transaction with
  cached lookups.
- payroll: sum(total_amount) per worker over a date range.
"""

from typing import Dict, Optional
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session

from app.core.db.engine import run_db
from app.core.exceptions import NotFoundError, ValidationError
from app.core.pagination import paginate_multi, build_paginated_response
from app.core.utils import search_words, normalize_unicode
from app.modules.users.models import User
from app.modules.operations.models import Operation
from app.modules.products.models import Product
from app.modules.stages.models import Stage
from app.modules.production.models import Batch
from .models import WorkLog
from .schemas import (
    WorkLogCreateDto,
    WorkLogBulkCreateDto,
    WorkLogUpdateDto,
    WorkLogResponse,
    BulkCreateResponse,
    PayrollLine,
    PayrollResponse,
    compute_duration_minutes,
)

ZERO = Decimal("0")
_CENTS = Decimal("0.01")


def _q(d: Decimal) -> Decimal:
    return d.quantize(_CENTS, rounding=ROUND_HALF_UP)


def _enriched_query():
    return (
        select(
            WorkLog, User.name, Operation.code, Operation.name,
            Operation.product_id, Product.part_no, Batch.batch_no, Stage.name,
        )
        .join(User, WorkLog.worker_id == User.id)
        .join(Operation, WorkLog.operation_id == Operation.id)
        .outerjoin(Product, Operation.product_id == Product.id)
        .outerjoin(Batch, WorkLog.batch_id == Batch.id)
        .outerjoin(Stage, WorkLog.stage_id == Stage.id)
        .where(WorkLog.deleted_at.is_(None))
    )


def _row_to_response(row) -> WorkLogResponse:
    wl, worker_name, op_code, op_name, product_id, part_no, batch_no, stage_name = row
    return WorkLogResponse(
        id=wl.id,
        worker_id=wl.worker_id,
        worker_name=worker_name,
        operation_id=wl.operation_id,
        operation_code=op_code,
        operation_name=op_name,
        product_id=product_id,
        product_part_no=part_no,
        batch_id=wl.batch_id,
        batch_no=batch_no,
        stage_id=wl.stage_id,
        stage_name=stage_name,
        variant=wl.variant,
        rate=wl.rate,
        quantity=wl.quantity,
        total_amount=wl.total_amount,
        work_date=wl.work_date,
        start_time=wl.start_time,
        end_time=wl.end_time,
        duration_minutes=wl.duration_minutes,
        notes=wl.notes,
        created_at=wl.created_at,
        updated_at=wl.updated_at,
        deleted_at=wl.deleted_at,
    )


# ----------------------------- validation helpers -----------------------------

def _require_user(db: Session, worker_id: int) -> User:
    u = db.execute(
        select(User).where(User.id == worker_id, User.deleted_at.is_(None))
    ).scalar_one_or_none()
    if not u:
        raise ValidationError(f"Worker {worker_id} does not exist")
    return u


def _require_existing(db: Session, model, ids: set, label: str):
    if not ids:
        return
    found = set(db.execute(
        select(model.id).where(model.id.in_(ids), model.deleted_at.is_(None))
    ).scalars().all())
    missing = ids - found
    if missing:
        raise ValidationError(f"{label} not found: {sorted(missing)}")


def _build_worklog(item, worker_id: int, op: Operation, now: datetime) -> WorkLog:
    """Build a WorkLog with snapshotted rate/total. rate = item override or operation rate."""
    rate = item.rate if item.rate is not None else op.rate
    if rate is None:
        raise ValidationError(
            f"Operation {op.id} ({op.code}) has no rate — provide a rate for this entry"
        )
    duration = (
        compute_duration_minutes(item.start_time, item.end_time)
        if item.start_time and item.end_time else None
    )
    return WorkLog(
        worker_id=worker_id,
        operation_id=op.id,
        batch_id=item.batch_id,
        stage_id=item.stage_id if item.stage_id is not None else op.stage_id,
        variant=normalize_unicode(item.variant) if item.variant else item.variant,
        work_date=item.work_date,
        start_time=item.start_time,
        end_time=item.end_time,
        quantity=item.quantity,
        rate=rate,
        total_amount=_q(item.quantity * rate),
        duration_minutes=duration,
        notes=normalize_unicode(item.notes) if item.notes else item.notes,
        created_at=now,
        updated_at=now,
    )


class WorkLogService:
    @staticmethod
    async def create(dto: WorkLogCreateDto) -> WorkLogResponse:
        def _create(db: Session) -> WorkLogResponse:
            _require_user(db, dto.worker_id)
            op = db.execute(
                select(Operation).where(
                    Operation.id == dto.operation_id, Operation.deleted_at.is_(None)
                )
            ).scalar_one_or_none()
            if not op:
                raise ValidationError(f"Operation {dto.operation_id} does not exist")
            if dto.batch_id is not None:
                _require_existing(db, Batch, {dto.batch_id}, "Batch")
            if dto.stage_id is not None:
                _require_existing(db, Stage, {dto.stage_id}, "Stage")

            now = datetime.utcnow()
            row = _build_worklog(dto, dto.worker_id, op, now)
            db.add(row)
            db.flush()
            return _row_to_response(
                db.execute(_enriched_query().where(WorkLog.id == row.id)).first()
            )

        return await run_db(_create)

    @staticmethod
    async def bulk_create(dto: WorkLogBulkCreateDto) -> BulkCreateResponse:
        def _bulk(db: Session) -> BulkCreateResponse:
            _require_user(db, dto.worker_id)

            op_ids = {it.operation_id for it in dto.items}
            ops: Dict[int, Operation] = {
                o.id: o for o in db.execute(
                    select(Operation).where(
                        Operation.id.in_(op_ids), Operation.deleted_at.is_(None)
                    )
                ).scalars().all()
            }
            missing_ops = op_ids - set(ops)
            if missing_ops:
                raise ValidationError(f"Operations not found: {sorted(missing_ops)}")

            _require_existing(db, Batch, {it.batch_id for it in dto.items if it.batch_id}, "Batch")
            _require_existing(db, Stage, {it.stage_id for it in dto.items if it.stage_id}, "Stage")

            now = datetime.utcnow()
            rows = [_build_worklog(it, dto.worker_id, ops[it.operation_id], now) for it in dto.items]
            db.add_all(rows)
            db.flush()

            ids = [r.id for r in rows]
            enriched = db.execute(
                _enriched_query().where(WorkLog.id.in_(ids)).order_by(WorkLog.id)
            ).all()
            items = [_row_to_response(r) for r in enriched]
            return BulkCreateResponse(created=len(items), items=items)

        return await run_db(_bulk)

    @staticmethod
    async def find_all_paginated(
        page: int = 1,
        page_size: int = 25,
        search: Optional[str] = None,
        worker_id: Optional[int] = None,
        operation_id: Optional[int] = None,
        batch_id: Optional[int] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> dict:
        words = search_words(search)

        def _find(db: Session) -> dict:
            query = _enriched_query()
            if worker_id is not None:
                query = query.where(WorkLog.worker_id == worker_id)
            if operation_id is not None:
                query = query.where(WorkLog.operation_id == operation_id)
            if batch_id is not None:
                query = query.where(WorkLog.batch_id == batch_id)
            if from_date is not None:
                query = query.where(WorkLog.work_date >= from_date)
            if to_date is not None:
                query = query.where(WorkLog.work_date <= to_date)
            for word in words:
                pattern = f"%{word}%"
                query = query.where(or_(
                    User.name.ilike(pattern),
                    Operation.code.ilike(pattern),
                    Operation.name.ilike(pattern),
                    WorkLog.notes.ilike(pattern),
                ))
            query = query.order_by(WorkLog.work_date.desc(), WorkLog.id.desc())

            rows, total = paginate_multi(db, query, page, page_size)
            items = [_row_to_response(r) for r in rows]
            return build_paginated_response(items, total, page, page_size)

        return await run_db(_find)

    @staticmethod
    async def find_one(log_id: int) -> WorkLogResponse:
        def _find(db: Session) -> WorkLogResponse:
            row = db.execute(_enriched_query().where(WorkLog.id == log_id)).first()
            if not row:
                raise NotFoundError("WorkLog", log_id)
            return _row_to_response(row)

        return await run_db(_find)

    @staticmethod
    async def update(log_id: int, dto: WorkLogUpdateDto) -> WorkLogResponse:
        def _update(db: Session) -> WorkLogResponse:
            row = db.execute(
                select(WorkLog).where(WorkLog.id == log_id, WorkLog.deleted_at.is_(None))
            ).scalar_one_or_none()
            if not row:
                raise NotFoundError("WorkLog", log_id)
            data = dto.model_dump(exclude_unset=True)
            if data.get("batch_id") is not None:
                _require_existing(db, Batch, {data["batch_id"]}, "Batch")
            if data.get("stage_id") is not None:
                _require_existing(db, Stage, {data["stage_id"]}, "Stage")
            for k, v in data.items():
                if k in ("variant", "notes") and isinstance(v, str):
                    v = normalize_unicode(v) or v
                setattr(row, k, v)
            # Recompute snapshots if rate/quantity changed; refresh duration if times present.
            if "rate" in data or "quantity" in data:
                row.total_amount = _q(row.quantity * row.rate)
            if row.start_time and row.end_time:
                row.duration_minutes = compute_duration_minutes(row.start_time, row.end_time)
            row.updated_at = datetime.utcnow()
            db.flush()
            return _row_to_response(
                db.execute(_enriched_query().where(WorkLog.id == log_id)).first()
            )

        return await run_db(_update)

    @staticmethod
    async def remove(log_id: int) -> None:
        def _remove(db: Session) -> None:
            row = db.execute(select(WorkLog).where(WorkLog.id == log_id)).scalar_one_or_none()
            if not row:
                raise NotFoundError("WorkLog", log_id)
            row.deleted_at = datetime.utcnow()
            db.flush()

        await run_db(_remove)

    @staticmethod
    async def payroll(
        from_date: date, to_date: date, worker_id: Optional[int] = None
    ) -> PayrollResponse:
        def _payroll(db: Session) -> PayrollResponse:
            q = (
                select(
                    WorkLog.worker_id, User.name,
                    func.count().label("entries"),
                    func.sum(WorkLog.quantity).label("qty"),
                    func.sum(WorkLog.total_amount).label("amount"),
                )
                .join(User, WorkLog.worker_id == User.id)
                .where(
                    WorkLog.deleted_at.is_(None),
                    WorkLog.work_date >= from_date,
                    WorkLog.work_date <= to_date,
                )
            )
            if worker_id is not None:
                q = q.where(WorkLog.worker_id == worker_id)
            q = q.group_by(WorkLog.worker_id, User.name).order_by(User.name)

            lines, grand = [], ZERO
            for wid, name, entries, qty, amount in db.execute(q).all():
                amount = amount or ZERO
                grand += amount
                lines.append(PayrollLine(
                    worker_id=wid, worker_name=name, entries=entries,
                    total_quantity=(qty or ZERO), total_amount=amount,
                ))
            return PayrollResponse(
                from_date=from_date, to_date=to_date, lines=lines, grand_total=grand
            )

        return await run_db(_payroll)
