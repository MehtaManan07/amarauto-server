"""
Job rates service. find_all with search; find_by_product(product_id).
"""

from typing import List, Optional
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from datetime import datetime
from decimal import Decimal

from app.core.db.engine import run_db
from app.core.exceptions import NotFoundError
from app.core.utils import search_words, normalize_unicode
from app.modules.products.models import Product
from .models import JobRate
from .schemas import JobRateCreateDto, JobRateUpdateDto, JobRateResponse


def _to_response(row: JobRate, product_part_no: Optional[str] = None) -> JobRateResponse:
    return JobRateResponse(
        id=row.id,
        product_id=row.product_id,
        product_part_no=product_part_no,
        operation_code=row.operation_code,
        operation_name=row.operation_name,
        rate=row.rate,
        sequence=row.sequence,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class JobRateService:
    @staticmethod
    async def create(dto: JobRateCreateDto) -> JobRateResponse:
        def _create(db: Session) -> JobRateResponse:
            product = db.execute(
                select(Product).where(
                    Product.id == dto.product_id,
                    Product.deleted_at.is_(None),
                )
            ).scalar_one_or_none()
            if not product:
                raise NotFoundError("Product", dto.product_id)
            row = JobRate(
                product_id=dto.product_id,
                operation_code=normalize_unicode(dto.operation_code) or dto.operation_code,
                operation_name=normalize_unicode(dto.operation_name) or dto.operation_name,
                rate=dto.rate,
                sequence=dto.sequence,
            )
            db.add(row)
            db.flush()
            db.refresh(row)
            return _to_response(row, product_part_no=product.part_no)
        return await run_db(_create)

    @staticmethod
    async def find_all(
        search: Optional[str] = None,
        product_id: Optional[int] = None,
    ) -> List[JobRateResponse]:
        """
        List non-deleted job rates. Optional search (operation_code, operation_name);
        optional product_id filter.
        """
        words = search_words(search)

        def _find_all(db: Session) -> List[JobRateResponse]:
            query = (
                select(JobRate, Product.part_no)
                .join(Product, JobRate.product_id == Product.id)
                .where(
                    JobRate.deleted_at.is_(None),
                    Product.deleted_at.is_(None),
                )
            )
            if product_id is not None:
                query = query.where(JobRate.product_id == product_id)
            for word in words:
                pattern = f"%{word}%"
                query = query.where(
                    or_(
                        JobRate.operation_code.ilike(pattern),
                        JobRate.operation_name.ilike(pattern),
                    )
                )
            query = query.order_by(JobRate.product_id, JobRate.sequence, JobRate.id)
            result = db.execute(query)
            rows = result.all()
            return [
                _to_response(line, product_part_no=part_no)
                for line, part_no in rows
            ]
        return await run_db(_find_all)

    @staticmethod
    async def find_by_product(product_id: int) -> List[JobRateResponse]:
        """Job rates for a product, ordered by sequence."""
        return await JobRateService.find_all(product_id=product_id)

    @staticmethod
    async def find_one(rate_id: int) -> JobRateResponse:
        def _find(db: Session) -> JobRateResponse:
            result = db.execute(
                select(JobRate, Product.part_no)
                .join(Product, JobRate.product_id == Product.id)
                .where(
                    JobRate.id == rate_id,
                    JobRate.deleted_at.is_(None),
                )
            )
            row = result.one_or_none()
            if not row:
                raise NotFoundError("JobRate", rate_id)
            line, part_no = row
            return _to_response(line, product_part_no=part_no)
        return await run_db(_find)

    @staticmethod
    async def update(rate_id: int, dto: JobRateUpdateDto) -> JobRateResponse:
        def _update(db: Session) -> JobRateResponse:
            result = db.execute(
                select(JobRate).where(
                    JobRate.id == rate_id,
                    JobRate.deleted_at.is_(None),
                )
            )
            row = result.scalar_one_or_none()
            if not row:
                raise NotFoundError("JobRate", rate_id)
            if dto.product_id is not None:
                product = db.execute(
                    select(Product).where(
                        Product.id == dto.product_id,
                        Product.deleted_at.is_(None),
                    )
                ).scalar_one_or_none()
                if not product:
                    raise NotFoundError("Product", dto.product_id)
            data = dto.model_dump(exclude_unset=True)
            for k, v in data.items():
                if k in ("operation_code", "operation_name") and isinstance(v, str):
                    v = normalize_unicode(v) or v
                setattr(row, k, v)
            db.flush()
            db.refresh(row)
            product = db.execute(
                select(Product).where(Product.id == row.product_id)
            ).scalar_one_or_none()
            return _to_response(row, product_part_no=product.part_no if product else None)
        return await run_db(_update)

    @staticmethod
    async def remove(rate_id: int) -> None:
        def _remove(db: Session) -> None:
            result = db.execute(select(JobRate).where(JobRate.id == rate_id))
            row = result.scalar_one_or_none()
            if not row:
                raise NotFoundError("JobRate", rate_id)
            row.deleted_at = datetime.utcnow()
            db.flush()
        await run_db(_remove)
