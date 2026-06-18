"""
Operations service. CRUD over the operations table (was job_rates).

List is paginated with optional search (code / name / component) and product_id /
stage_id filters — the recipe editor lists a product's operations by stage. Responses
are enriched with product_part_no + stage_name via a join. `code` is unique (it is the
worklog resolution key); product_id and stage_id FKs are validated on write.
"""

from typing import Optional
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.db.engine import run_db
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.pagination import paginate_multi, build_paginated_response
from app.core.utils import search_words, normalize_unicode
from app.modules.operations.models import Operation
from app.modules.products.models import Product
from app.modules.stages.models import Stage
from app.modules.operations.schemas import (
    OperationCreateDto,
    OperationUpdateDto,
    OperationResponse,
)


def _to_response(
    row: Operation,
    product_part_no: Optional[str] = None,
    stage_name: Optional[str] = None,
) -> OperationResponse:
    return OperationResponse(
        id=row.id,
        product_id=row.product_id,
        stage_id=row.stage_id,
        code=row.code,
        name=row.name,
        rate=row.rate,
        sequence=row.sequence,
        component=row.component,
        side=row.side,
        product_hint=row.product_hint,
        product_part_no=product_part_no,
        stage_name=stage_name,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )


def _enriched_query():
    """Operation rows joined to part_no + stage name. BOTH are OUTER joins: product_id is
    nullable (unmapped ops) and stage_id is nullable."""
    return (
        select(Operation, Product.part_no, Stage.name)
        .outerjoin(Product, Operation.product_id == Product.id)
        .outerjoin(Stage, Operation.stage_id == Stage.id)
        .where(Operation.deleted_at.is_(None))
    )


def _require_product(db: Session, product_id: int) -> Product:
    product = db.execute(
        select(Product).where(Product.id == product_id, Product.deleted_at.is_(None))
    ).scalar_one_or_none()
    if not product:
        raise ValidationError(f"Product {product_id} does not exist")
    return product


def _require_stage(db: Session, stage_id: int) -> Stage:
    stage = db.execute(
        select(Stage).where(Stage.id == stage_id, Stage.deleted_at.is_(None))
    ).scalar_one_or_none()
    if not stage:
        raise ValidationError(f"Stage {stage_id} does not exist")
    return stage


def _guard_unique_code(db: Session, code: str, exclude_id: Optional[int] = None) -> None:
    query = select(Operation.id).where(
        Operation.code == code, Operation.deleted_at.is_(None)
    )
    if exclude_id is not None:
        query = query.where(Operation.id != exclude_id)
    if db.execute(query).first():
        raise ConflictError("An operation with this code already exists")


class OperationService:
    @staticmethod
    async def create(dto: OperationCreateDto) -> OperationResponse:
        def _create(db: Session) -> OperationResponse:
            # product_id is optional — omit for an unmapped op (assign a product later).
            product = _require_product(db, dto.product_id) if dto.product_id is not None else None
            stage = _require_stage(db, dto.stage_id) if dto.stage_id is not None else None
            _guard_unique_code(db, dto.code)

            now = datetime.utcnow()
            row = Operation(
                product_id=dto.product_id,
                stage_id=dto.stage_id,
                code=dto.code,
                name=normalize_unicode(dto.name) or dto.name,
                rate=dto.rate,
                sequence=dto.sequence,
                component=normalize_unicode(dto.component) if dto.component else dto.component,
                side=dto.side,
                product_hint=normalize_unicode(dto.product_hint) if dto.product_hint else dto.product_hint,
                created_at=now,
                updated_at=now,
            )
            db.add(row)
            db.flush()
            return _to_response(row, product.part_no if product else None, stage.name if stage else None)

        return await run_db(_create)

    @staticmethod
    async def find_all_paginated(
        page: int = 1,
        page_size: int = 25,
        search: Optional[str] = None,
        product_id: Optional[int] = None,
        stage_id: Optional[int] = None,
        unmapped: Optional[bool] = None,
    ) -> dict:
        words = search_words(search)

        def _find(db: Session) -> dict:
            query = _enriched_query()
            if unmapped is True:
                query = query.where(Operation.product_id.is_(None))
            elif unmapped is False:
                query = query.where(Operation.product_id.isnot(None))
            if product_id is not None:
                query = query.where(Operation.product_id == product_id)
            if stage_id is not None:
                query = query.where(Operation.stage_id == stage_id)
            for word in words:
                pattern = f"%{word}%"
                query = query.where(
                    or_(
                        Operation.code.ilike(pattern),
                        Operation.name.ilike(pattern),
                        Operation.component.ilike(pattern),
                        Operation.product_hint.ilike(pattern),
                    )
                )
            # Stable, useful order: by product, then stage sequence-ish, then op sequence.
            query = query.order_by(
                Operation.product_id, Operation.stage_id, Operation.sequence, Operation.id
            )
            rows, total = paginate_multi(db, query, page, page_size)
            items = [_to_response(op, part_no, stage_name) for (op, part_no, stage_name) in rows]
            return build_paginated_response(items, total, page, page_size)

        return await run_db(_find)

    @staticmethod
    async def find_one(operation_id: int) -> OperationResponse:
        def _find(db: Session) -> OperationResponse:
            result = db.execute(
                _enriched_query().where(Operation.id == operation_id)
            ).first()
            if not result:
                raise NotFoundError("Operation", operation_id)
            op, part_no, stage_name = result
            return _to_response(op, part_no, stage_name)

        return await run_db(_find)

    @staticmethod
    async def update(operation_id: int, dto: OperationUpdateDto) -> OperationResponse:
        def _update(db: Session) -> OperationResponse:
            row = db.execute(
                select(Operation).where(
                    Operation.id == operation_id, Operation.deleted_at.is_(None)
                )
            ).scalar_one_or_none()
            if not row:
                raise NotFoundError("Operation", operation_id)

            data = dto.model_dump(exclude_unset=True)
            if "product_id" in data and data["product_id"] is not None:
                _require_product(db, data["product_id"])
            if "stage_id" in data and data["stage_id"] is not None:
                _require_stage(db, data["stage_id"])
            if "code" in data and data["code"] is not None:
                _guard_unique_code(db, data["code"], exclude_id=operation_id)

            text_fields = ("name", "component", "product_hint")
            for k, v in data.items():
                if k in text_fields and isinstance(v, str):
                    v = normalize_unicode(v) or v
                setattr(row, k, v)
            row.updated_at = datetime.utcnow()
            db.flush()

            part_no = db.execute(
                select(Product.part_no).where(Product.id == row.product_id)
            ).scalar_one_or_none()
            stage_name = (
                db.execute(
                    select(Stage.name).where(Stage.id == row.stage_id)
                ).scalar_one_or_none()
                if row.stage_id is not None
                else None
            )
            return _to_response(row, part_no, stage_name)

        return await run_db(_update)

    @staticmethod
    async def remove(operation_id: int) -> None:
        def _remove(db: Session) -> None:
            row = db.execute(
                select(Operation).where(Operation.id == operation_id)
            ).scalar_one_or_none()
            if not row:
                raise NotFoundError("Operation", operation_id)
            row.deleted_at = datetime.utcnow()
            db.flush()

        await run_db(_remove)
