"""
Work log service. CRUD with pagination and filters.
"""

from typing import Optional
from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session
from datetime import date, datetime
from decimal import Decimal

from app.core.db.engine import run_db
from app.core.exceptions import NotFoundError
from app.core.pagination import paginate_query, build_paginated_response
from app.core.utils import search_words, normalize_text_fields
from app.modules.users.models import User
from app.modules.job_rates.models import JobRate
from app.modules.products.models import Product
from .models import WorkLog
from .schemas import (
    WorkLogCreateDto,
    WorkLogUpdateDto,
    WorkLogResponse,
    WorkLogPaginatedResponse,
)


def _to_response(
    row: WorkLog,
    user_name: Optional[str] = None,
    product_id: Optional[int] = None,
    product_part_no: Optional[str] = None,
    product_name: Optional[str] = None,
    operation_code: Optional[str] = None,
    operation_name: Optional[str] = None,
) -> WorkLogResponse:
    return WorkLogResponse(
        id=row.id,
        user_id=row.user_id,
        user_name=user_name,
        job_rate_id=row.job_rate_id,
        product_id=product_id,
        product_part_no=product_part_no,
        product_name=product_name,
        operation_code=operation_code,
        operation_name=operation_name,
        rate=row.rate,
        quantity=row.quantity,
        total_amount=row.total_amount,
        work_date=row.work_date,
        duration_minutes=row.duration_minutes,
        notes=row.notes,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class WorkLogService:
    @staticmethod
    async def create(dto: WorkLogCreateDto) -> WorkLogResponse:
        def _create(db: Session) -> WorkLogResponse:
            user = db.execute(
                select(User).where(
                    User.id == dto.user_id,
                    User.deleted_at.is_(None),
                )
            ).scalar_one_or_none()
            if not user:
                raise NotFoundError("User", dto.user_id)
            job_rate = db.execute(
                select(JobRate, Product.part_no, Product.name)
                .join(Product, JobRate.product_id == Product.id)
                .where(
                    JobRate.id == dto.job_rate_id,
                    JobRate.deleted_at.is_(None),
                )
            ).one_or_none()
            if not job_rate:
                raise NotFoundError("JobRate", dto.job_rate_id)
            jr, part_no, prod_name = job_rate
            rate = jr.rate
            total_amount = dto.quantity * rate
            notes = normalize_text_fields({"notes": dto.notes}, ("notes",)).get("notes")
            row = WorkLog(
                user_id=dto.user_id,
                job_rate_id=dto.job_rate_id,
                work_date=dto.work_date,
                quantity=dto.quantity,
                rate=rate,
                total_amount=total_amount,
                duration_minutes=dto.duration_minutes,
                notes=notes,
            )
            db.add(row)
            db.flush()
            db.refresh(row)
            return _to_response(
                row,
                user_name=user.name,
                product_id=jr.product_id,
                product_part_no=part_no,
                product_name=prod_name,
                operation_code=jr.operation_code,
                operation_name=jr.operation_name,
            )
        return await run_db(_create)

    @staticmethod
    async def find_all_paginated(
        page: int = 1,
        page_size: int = 25,
        user_id: Optional[int] = None,
        product_id: Optional[int] = None,
        job_rate_id: Optional[int] = None,
        work_date_from: Optional[date] = None,
        work_date_to: Optional[date] = None,
        search: Optional[str] = None,
    ) -> WorkLogPaginatedResponse:
        words = search_words(search)

        def _find_all(db: Session) -> WorkLogPaginatedResponse:
            query = (
                select(
                    WorkLog,
                    User.name,
                    Product.id,
                    Product.part_no,
                    Product.name,
                    JobRate.operation_code,
                    JobRate.operation_name,
                )
                .join(User, WorkLog.user_id == User.id)
                .join(JobRate, WorkLog.job_rate_id == JobRate.id)
                .join(Product, JobRate.product_id == Product.id)
                .where(
                    WorkLog.deleted_at.is_(None),
                    User.deleted_at.is_(None),
                    JobRate.deleted_at.is_(None),
                    Product.deleted_at.is_(None),
                )
            )
            if user_id is not None:
                query = query.where(WorkLog.user_id == user_id)
            if product_id is not None:
                query = query.where(JobRate.product_id == product_id)
            if job_rate_id is not None:
                query = query.where(WorkLog.job_rate_id == job_rate_id)
            if work_date_from is not None:
                query = query.where(WorkLog.work_date >= work_date_from)
            if work_date_to is not None:
                query = query.where(WorkLog.work_date <= work_date_to)
            for word in words:
                pattern = f"%{word}%"
                query = query.where(
                    or_(
                        User.name.ilike(pattern),
                        Product.name.ilike(pattern),
                        Product.part_no.ilike(pattern),
                        JobRate.operation_code.ilike(pattern),
                        JobRate.operation_name.ilike(pattern),
                    )
                )
            query = query.order_by(WorkLog.work_date.desc(), WorkLog.created_at.desc())

            items, total = paginate_query(db, query, page, page_size)
            result = [
                _to_response(
                    wl,
                    user_name=uname,
                    product_id=pid,
                    product_part_no=ppart,
                    product_name=pname,
                    operation_code=opcode,
                    operation_name=opname,
                )
                for wl, uname, pid, ppart, pname, opcode, opname in items
            ]
            return WorkLogPaginatedResponse(
                **build_paginated_response(result, total, page, page_size)
            )
        return await run_db(_find_all)

    @staticmethod
    async def find_one(log_id: int) -> WorkLogResponse:
        def _find(db: Session) -> WorkLogResponse:
            result = db.execute(
                select(
                    WorkLog,
                    User.name,
                    Product.id,
                    Product.part_no,
                    Product.name,
                    JobRate.operation_code,
                    JobRate.operation_name,
                )
                .join(User, WorkLog.user_id == User.id)
                .join(JobRate, WorkLog.job_rate_id == JobRate.id)
                .join(Product, JobRate.product_id == Product.id)
                .where(
                    WorkLog.id == log_id,
                    WorkLog.deleted_at.is_(None),
                )
            )
            row = result.one_or_none()
            if not row:
                raise NotFoundError("WorkLog", log_id)
            wl, uname, pid, ppart, pname, opcode, opname = row
            return _to_response(
                wl,
                user_name=uname,
                product_id=pid,
                product_part_no=ppart,
                product_name=pname,
                operation_code=opcode,
                operation_name=opname,
            )
        return await run_db(_find)

    @staticmethod
    async def update(log_id: int, dto: WorkLogUpdateDto) -> WorkLogResponse:
        def _update(db: Session) -> WorkLogResponse:
            result = db.execute(
                select(WorkLog).where(
                    WorkLog.id == log_id,
                    WorkLog.deleted_at.is_(None),
                )
            )
            row = result.scalar_one_or_none()
            if not row:
                raise NotFoundError("WorkLog", log_id)
            data = dto.model_dump(exclude_unset=True)
            data = normalize_text_fields(data, ("notes",))
            if "user_id" in data:
                user = db.execute(
                    select(User).where(
                        User.id == data["user_id"],
                        User.deleted_at.is_(None),
                    )
                ).scalar_one_or_none()
                if not user:
                    raise NotFoundError("User", data["user_id"])
            if "job_rate_id" in data:
                jr_result = db.execute(
                    select(JobRate).where(
                        JobRate.id == data["job_rate_id"],
                        JobRate.deleted_at.is_(None),
                    )
                ).scalar_one_or_none()
                if not jr_result:
                    raise NotFoundError("JobRate", data["job_rate_id"])
                row.rate = jr_result.rate
            for k, v in data.items():
                setattr(row, k, v)
            row.total_amount = row.quantity * row.rate
            db.flush()
            db.refresh(row)
            res = db.execute(
                select(
                    WorkLog,
                    User.name,
                    Product.id,
                    Product.part_no,
                    Product.name,
                    JobRate.operation_code,
                    JobRate.operation_name,
                )
                .join(User, WorkLog.user_id == User.id)
                .join(JobRate, WorkLog.job_rate_id == JobRate.id)
                .join(Product, JobRate.product_id == Product.id)
                .where(WorkLog.id == log_id)
            )
            wl, uname, pid, ppart, pname, opcode, opname = res.one()
            return _to_response(
                wl,
                user_name=uname,
                product_id=pid,
                product_part_no=ppart,
                product_name=pname,
                operation_code=opcode,
                operation_name=opname,
            )
        return await run_db(_update)

    @staticmethod
    async def remove(log_id: int) -> None:
        def _remove(db: Session) -> None:
            result = db.execute(select(WorkLog).where(WorkLog.id == log_id))
            row = result.scalar_one_or_none()
            if not row:
                raise NotFoundError("WorkLog", log_id)
            row.deleted_at = datetime.utcnow()
            db.flush()
        await run_db(_remove)
