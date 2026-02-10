"""
BOM service. find_all with search; find_by_product(product_id, variant).
"""

from typing import List, Optional
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from datetime import datetime
from decimal import Decimal

from app.core.db.engine import run_db
from app.core.exceptions import NotFoundError
from app.core.utils import search_words
from app.modules.products.models import Product
from app.modules.raw_materials.models import RawMaterial
from .models import BOMLine
from .schemas import BOMLineCreateDto, BOMLineUpdateDto, BOMLineResponse


def _to_response(row: BOMLine, raw_material_name: Optional[str] = None) -> BOMLineResponse:
    return BOMLineResponse(
        id=row.id,
        product_id=row.product_id,
        raw_material_id=row.raw_material_id,
        raw_material_name=raw_material_name,
        variant=row.variant,
        batch_qty=row.batch_qty,
        raw_qty=row.raw_qty,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class BOMService:
    @staticmethod
    async def create(dto: BOMLineCreateDto) -> BOMLineResponse:
        def _create(db: Session) -> BOMLineResponse:
            product = db.execute(
                select(Product).where(
                    Product.id == dto.product_id,
                    Product.deleted_at.is_(None),
                )
            ).scalar_one_or_none()
            if not product:
                raise NotFoundError("Product", dto.product_id)
            raw = db.execute(
                select(RawMaterial).where(
                    RawMaterial.id == dto.raw_material_id,
                    RawMaterial.deleted_at.is_(None),
                )
            ).scalar_one_or_none()
            if not raw:
                raise NotFoundError("RawMaterial", dto.raw_material_id)
            row = BOMLine(
                product_id=dto.product_id,
                raw_material_id=dto.raw_material_id,
                variant=dto.variant,
                batch_qty=dto.batch_qty,
                raw_qty=dto.raw_qty,
            )
            db.add(row)
            db.flush()
            db.refresh(row)
            return _to_response(row, raw_material_name=raw.name)
        return await run_db(_create)

    @staticmethod
    async def find_all(
        search: Optional[str] = None,
        product_id: Optional[int] = None,
        variant: Optional[str] = None,
    ) -> List[BOMLineResponse]:
        """
        List non-deleted BOM lines. Optional search (raw material name, variant);
        optional product_id and variant filters.
        """
        words = search_words(search)

        def _find_all(db: Session) -> List[BOMLineResponse]:
            query = (
                select(BOMLine, RawMaterial.name)
                .join(RawMaterial, BOMLine.raw_material_id == RawMaterial.id)
                .where(
                    BOMLine.deleted_at.is_(None),
                    RawMaterial.deleted_at.is_(None),
                )
            )
            if product_id is not None:
                query = query.where(BOMLine.product_id == product_id)
            if variant is not None:
                query = query.where(BOMLine.variant == variant)
            for word in words:
                pattern = f"%{word}%"
                query = query.where(
                    or_(
                        RawMaterial.name.ilike(pattern),
                        BOMLine.variant.ilike(pattern),
                    )
                )
            query = query.order_by(BOMLine.product_id, BOMLine.variant, BOMLine.id)
            result = db.execute(query)
            rows = result.all()
            return [
                _to_response(line, raw_material_name=rm_name)
                for line, rm_name in rows
            ]
        return await run_db(_find_all)

    @staticmethod
    async def find_by_product(
        product_id: int,
        variant: Optional[str] = None,
    ) -> List[BOMLineResponse]:
        """BOM lines for a product (and optional variant). Used by products get_bom."""
        return await BOMService.find_all(
            product_id=product_id,
            variant=variant,
        )

    @staticmethod
    async def find_one(line_id: int) -> BOMLineResponse:
        def _find(db: Session) -> BOMLineResponse:
            result = db.execute(
                select(BOMLine, RawMaterial.name)
                .join(RawMaterial, BOMLine.raw_material_id == RawMaterial.id)
                .where(
                    BOMLine.id == line_id,
                    BOMLine.deleted_at.is_(None),
                )
            )
            row = result.one_or_none()
            if not row:
                raise NotFoundError("BOMLine", line_id)
            line, rm_name = row
            return _to_response(line, raw_material_name=rm_name)
        return await run_db(_find)

    @staticmethod
    async def update(line_id: int, dto: BOMLineUpdateDto) -> BOMLineResponse:
        def _update(db: Session) -> BOMLineResponse:
            result = db.execute(
                select(BOMLine).where(
                    BOMLine.id == line_id,
                    BOMLine.deleted_at.is_(None),
                )
            )
            row = result.scalar_one_or_none()
            if not row:
                raise NotFoundError("BOMLine", line_id)
            if dto.product_id is not None:
                product = db.execute(
                    select(Product).where(
                        Product.id == dto.product_id,
                        Product.deleted_at.is_(None),
                    )
                ).scalar_one_or_none()
                if not product:
                    raise NotFoundError("Product", dto.product_id)
            if dto.raw_material_id is not None:
                raw = db.execute(
                    select(RawMaterial).where(
                        RawMaterial.id == dto.raw_material_id,
                        RawMaterial.deleted_at.is_(None),
                    )
                ).scalar_one_or_none()
                if not raw:
                    raise NotFoundError("RawMaterial", dto.raw_material_id)
            data = dto.model_dump(exclude_unset=True)
            for k, v in data.items():
                setattr(row, k, v)
            db.flush()
            db.refresh(row)
            raw = db.execute(
                select(RawMaterial).where(RawMaterial.id == row.raw_material_id)
            ).scalar_one_or_none()
            return _to_response(row, raw_material_name=raw.name if raw else None)
        return await run_db(_update)

    @staticmethod
    async def remove(line_id: int) -> None:
        def _remove(db: Session) -> None:
            result = db.execute(select(BOMLine).where(BOMLine.id == line_id))
            row = result.scalar_one_or_none()
            if not row:
                raise NotFoundError("BOMLine", line_id)
            row.deleted_at = datetime.utcnow()
            db.flush()
        await run_db(_remove)
