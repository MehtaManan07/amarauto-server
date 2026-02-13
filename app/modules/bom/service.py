"""
BOM service. find_all with search; find_by_product(product_id, variant).
"""

from typing import List, Optional
from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session
from datetime import datetime
from decimal import Decimal

from app.core.db.engine import run_db
from app.core.exceptions import NotFoundError
from app.core.pagination import build_paginated_response
from app.core.utils import search_words, normalize_unicode
from app.modules.products.models import Product
from app.modules.raw_materials.models import RawMaterial
from .models import BOMLine
from .schemas import (
    BOMLineCreateDto,
    BOMLineUpdateDto,
    BOMLineResponse,
    ProductionCalcLineResponse,
    ProductionCalcResponse,
)


def _to_response(
    row: BOMLine,
    raw_material_name: Optional[str] = None,
    product_name: Optional[str] = None,
    product_part_no: Optional[str] = None,
) -> BOMLineResponse:
    return BOMLineResponse(
        id=row.id,
        product_id=row.product_id,
        raw_material_id=row.raw_material_id,
        product_name=product_name,
        product_part_no=product_part_no,
        raw_material_name=raw_material_name,
        variant=row.variant,
        stage_number=getattr(row, "stage_number", 1),
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
                variant=normalize_unicode(dto.variant) if dto.variant else dto.variant,
                stage_number=dto.stage_number,
                batch_qty=dto.batch_qty,
                raw_qty=dto.raw_qty,
            )
            db.add(row)
            db.flush()
            db.refresh(row)
            return _to_response(
                row,
                raw_material_name=raw.name,
                product_name=product.name,
                product_part_no=product.part_no,
            )
        return await run_db(_create)

    @staticmethod
    async def find_all(
        search: Optional[str] = None,
        product_id: Optional[int] = None,
        raw_material_id: Optional[int] = None,
        variant: Optional[str] = None,
    ) -> List[BOMLineResponse]:
        """
        List non-deleted BOM lines. Optional search (raw material name, variant);
        optional product_id, raw_material_id and variant filters.
        """
        words = search_words(search)

        def _find_all(db: Session) -> List[BOMLineResponse]:
            query = (
                select(BOMLine, RawMaterial.name, Product.name, Product.part_no)
                .join(RawMaterial, BOMLine.raw_material_id == RawMaterial.id)
                .join(Product, BOMLine.product_id == Product.id)
                .where(
                    BOMLine.deleted_at.is_(None),
                    RawMaterial.deleted_at.is_(None),
                    Product.deleted_at.is_(None),
                )
            )
            if product_id is not None:
                query = query.where(BOMLine.product_id == product_id)
            if raw_material_id is not None:
                query = query.where(BOMLine.raw_material_id == raw_material_id)
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
                _to_response(
                    line,
                    raw_material_name=rm_name,
                    product_name=prod_name,
                    product_part_no=prod_part_no,
                )
                for line, rm_name, prod_name, prod_part_no in rows
            ]
        return await run_db(_find_all)

    @staticmethod
    async def find_all_paginated(
        page: int = 1,
        page_size: int = 25,
        search: Optional[str] = None,
        product_id: Optional[int] = None,
        raw_material_id: Optional[int] = None,
        variant: Optional[str] = None,
    ) -> dict:
        """
        List BOM lines with pagination. Optional search, product_id, raw_material_id, variant filters.
        """
        words = search_words(search)

        def _find_all_paginated(db: Session) -> dict:
            query = (
                select(BOMLine, RawMaterial.name, Product.name, Product.part_no)
                .join(RawMaterial, BOMLine.raw_material_id == RawMaterial.id)
                .join(Product, BOMLine.product_id == Product.id)
                .where(
                    BOMLine.deleted_at.is_(None),
                    RawMaterial.deleted_at.is_(None),
                    Product.deleted_at.is_(None),
                )
            )
            if product_id is not None:
                query = query.where(BOMLine.product_id == product_id)
            if raw_material_id is not None:
                query = query.where(BOMLine.raw_material_id == raw_material_id)
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

            count_query = select(func.count()).select_from(query.subquery())
            total = db.execute(count_query).scalar() or 0

            offset = (page - 1) * page_size
            paginated_query = query.offset(offset).limit(page_size)
            result = db.execute(paginated_query)
            rows = result.all()

            items = [
                _to_response(
                    line,
                    raw_material_name=rm_name,
                    product_name=prod_name,
                    product_part_no=prod_part_no,
                )
                for line, rm_name, prod_name, prod_part_no in rows
            ]
            return build_paginated_response(items, total, page, page_size)

        return await run_db(_find_all_paginated)

    @staticmethod
    async def get_variants(product_id: int) -> List[str]:
        """Return distinct variants for a product from BOM lines."""
        def _get_variants(db: Session) -> List[str]:
            stmt = (
                select(BOMLine.variant)
                .where(
                    BOMLine.product_id == product_id,
                    BOMLine.deleted_at.is_(None),
                    BOMLine.variant.isnot(None),
                )
                .distinct()
                .order_by(BOMLine.variant)
            )
            result = db.execute(stmt)
            return [r for r in result.scalars().all() if r]

        return await run_db(_get_variants)

    @staticmethod
    async def get_production_calc(
        product_id: int,
        variant: Optional[str],
        quantity: int,
    ) -> ProductionCalcResponse:
        """
        Calculate material requirements for producing `quantity` units.
        Aggregates by raw material; returns shortage, order cost, max producible units.
        """
        def _calc(db: Session) -> ProductionCalcResponse:
            product = db.execute(
                select(Product).where(
                    Product.id == product_id,
                    Product.deleted_at.is_(None),
                )
            ).scalar_one_or_none()
            if not product:
                raise NotFoundError("Product", product_id)

            bom_query = (
                select(BOMLine, RawMaterial)
                .join(RawMaterial, BOMLine.raw_material_id == RawMaterial.id)
                .where(
                    BOMLine.product_id == product_id,
                    BOMLine.deleted_at.is_(None),
                    RawMaterial.deleted_at.is_(None),
                )
            )
            if variant is not None:
                bom_query = bom_query.where(BOMLine.variant == variant)
            bom_query = bom_query.order_by(BOMLine.raw_material_id)
            result = db.execute(bom_query)
            rows = result.all()

            # Aggregate by raw_material_id (same material can appear multiple times in BOM)
            by_rm: dict[int, tuple[Decimal, RawMaterial]] = {}
            for line, raw in rows:
                needed_per_unit = line.raw_qty / line.batch_qty if line.batch_qty else Decimal("0")
                total_needed = needed_per_unit * quantity
                if raw.id in by_rm:
                    prev_needed, _ = by_rm[raw.id]
                    by_rm[raw.id] = (prev_needed + total_needed, raw)
                else:
                    by_rm[raw.id] = (total_needed, raw)

            lines: List[ProductionCalcLineResponse] = []
            total_order_cost = Decimal("0")
            max_producible = float("inf")

            for raw_id, (needed_qty, raw) in by_rm.items():
                current_stock = raw.stock_qty or Decimal("0")
                shortage = max(Decimal("0"), needed_qty - current_stock)
                status = "ok" if shortage == 0 else "low"
                price = raw.purchase_price or Decimal("0")
                order_cost = shortage * price
                total_order_cost += order_cost

                needed_per_unit = needed_qty / quantity if quantity else Decimal("0")
                if needed_per_unit > 0:
                    can_make = int(float(current_stock) / float(needed_per_unit))
                    max_producible = min(max_producible, can_make)

                lines.append(
                    ProductionCalcLineResponse(
                        raw_material_name=raw.name,
                        unit_type=raw.unit_type,
                        needed_qty=needed_qty,
                        current_stock=current_stock,
                        shortage=shortage,
                        status=status,
                        purchase_price=raw.purchase_price,
                        order_cost=order_cost,
                    )
                )

            if not by_rm:
                max_producible = 0
            elif max_producible == float("inf"):
                max_producible = quantity

            return ProductionCalcResponse(
                product_part_no=product.part_no,
                product_name=product.name,
                variant=variant,
                quantity=quantity,
                lines=lines,
                total_order_cost=total_order_cost,
                max_producible_units=int(max_producible),
            )

        return await run_db(_calc)

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
                select(BOMLine, RawMaterial.name, Product.name, Product.part_no)
                .join(RawMaterial, BOMLine.raw_material_id == RawMaterial.id)
                .join(Product, BOMLine.product_id == Product.id)
                .where(
                    BOMLine.id == line_id,
                    BOMLine.deleted_at.is_(None),
                )
            )
            row = result.one_or_none()
            if not row:
                raise NotFoundError("BOMLine", line_id)
            line, rm_name, prod_name, prod_part_no = row
            return _to_response(
                line,
                raw_material_name=rm_name,
                product_name=prod_name,
                product_part_no=prod_part_no,
            )
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
                if k == "variant" and isinstance(v, str):
                    v = normalize_unicode(v) or v
                setattr(row, k, v)
            db.flush()
            db.refresh(row)
            raw = db.execute(
                select(RawMaterial).where(RawMaterial.id == row.raw_material_id)
            ).scalar_one_or_none()
            product = db.execute(
                select(Product).where(Product.id == row.product_id)
            ).scalar_one_or_none()
            return _to_response(
                row,
                raw_material_name=raw.name if raw else None,
                product_name=product.name if product else None,
                product_part_no=product.part_no if product else None,
            )
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
