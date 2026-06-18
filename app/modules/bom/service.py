"""
BOM service (new production-flow schema). CRUD + list (paginated, filterable),
distinct style/colour variants per product, and a production calculator.

Quantity basis: per_unit = qty_per_batch / batch_size (batch_size > 0, enforced by DTO).
Duplicate lines are SUMMED, never deduped — create always adds a distinct line, and the
production calculator aggregates per raw material across all of a variant's lines.
"""

from typing import List, Optional
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from datetime import datetime
from decimal import Decimal

from app.core.db.engine import run_db
from app.core.exceptions import NotFoundError, ValidationError
from app.core.pagination import paginate_multi, build_paginated_response
from app.core.utils import search_words, normalize_unicode
from app.modules.products.models import Product
from app.modules.raw_materials.models import RawMaterial
from app.modules.stages.models import Stage
from .models import BOMLine
from .schemas import (
    BOMLineCreateDto,
    BOMLineUpdateDto,
    BOMLineResponse,
    BOMVariantResponse,
    ProductionCalcLineResponse,
    ProductionCalcResponse,
)


def _per_unit(qty_per_batch: Decimal, batch_size: Decimal) -> Optional[Decimal]:
    if not batch_size:
        return None
    return qty_per_batch / batch_size


def _to_response(
    row: BOMLine,
    raw_material_name: Optional[str] = None,
    raw_material_unit: Optional[str] = None,
    product_name: Optional[str] = None,
    product_part_no: Optional[str] = None,
    stage_name: Optional[str] = None,
) -> BOMLineResponse:
    return BOMLineResponse(
        id=row.id,
        product_id=row.product_id,
        stage_id=row.stage_id,
        raw_material_id=row.raw_material_id,
        style=row.style,
        colour=row.colour,
        batch_size=row.batch_size,
        qty_per_batch=row.qty_per_batch,
        per_unit=_per_unit(row.qty_per_batch, row.batch_size),
        product_name=product_name,
        product_part_no=product_part_no,
        raw_material_name=raw_material_name,
        raw_material_unit=raw_material_unit,
        stage_name=stage_name,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )


def _enriched_query():
    """BOM rows joined to material (name/unit), product (name/part_no), stage (name).
    Stage is an OUTER join — stage_id is nullable."""
    return (
        select(BOMLine, RawMaterial.name, RawMaterial.unit_type, Product.name, Product.part_no, Stage.name)
        .join(RawMaterial, BOMLine.raw_material_id == RawMaterial.id)
        .join(Product, BOMLine.product_id == Product.id)
        .outerjoin(Stage, BOMLine.stage_id == Stage.id)
        .where(
            BOMLine.deleted_at.is_(None),
            RawMaterial.deleted_at.is_(None),
            Product.deleted_at.is_(None),
        )
    )


def _row_to_response(row) -> BOMLineResponse:
    line, rm_name, rm_unit, prod_name, prod_part_no, stage_name = row
    return _to_response(
        line,
        raw_material_name=rm_name,
        raw_material_unit=rm_unit,
        product_name=prod_name,
        product_part_no=prod_part_no,
        stage_name=stage_name,
    )


def _require_product(db: Session, product_id: int) -> Product:
    product = db.execute(
        select(Product).where(Product.id == product_id, Product.deleted_at.is_(None))
    ).scalar_one_or_none()
    if not product:
        raise ValidationError(f"Product {product_id} does not exist")
    return product


def _require_raw_material(db: Session, raw_material_id: int) -> RawMaterial:
    raw = db.execute(
        select(RawMaterial).where(
            RawMaterial.id == raw_material_id, RawMaterial.deleted_at.is_(None)
        )
    ).scalar_one_or_none()
    if not raw:
        raise ValidationError(f"Raw material {raw_material_id} does not exist")
    return raw


def _require_stage(db: Session, stage_id: int) -> Stage:
    stage = db.execute(
        select(Stage).where(Stage.id == stage_id, Stage.deleted_at.is_(None))
    ).scalar_one_or_none()
    if not stage:
        raise ValidationError(f"Stage {stage_id} does not exist")
    return stage


class BOMService:
    @staticmethod
    async def create(dto: BOMLineCreateDto) -> BOMLineResponse:
        def _create(db: Session) -> BOMLineResponse:
            product = _require_product(db, dto.product_id)
            raw = _require_raw_material(db, dto.raw_material_id)
            stage = _require_stage(db, dto.stage_id) if dto.stage_id is not None else None

            # No dedup/merge: duplicate lines are intentional (sum-don't-dedup).
            now = datetime.utcnow()
            row = BOMLine(
                product_id=dto.product_id,
                raw_material_id=dto.raw_material_id,
                stage_id=dto.stage_id,
                style=normalize_unicode(dto.style) if dto.style else dto.style,
                colour=normalize_unicode(dto.colour) if dto.colour else dto.colour,
                batch_size=dto.batch_size,
                qty_per_batch=dto.qty_per_batch,
                created_at=now,
                updated_at=now,
            )
            db.add(row)
            db.flush()
            return _to_response(
                row,
                raw_material_name=raw.name,
                raw_material_unit=raw.unit_type,
                product_name=product.name,
                product_part_no=product.part_no,
                stage_name=stage.name if stage else None,
            )

        return await run_db(_create)

    @staticmethod
    async def find_all_paginated(
        page: int = 1,
        page_size: int = 25,
        search: Optional[str] = None,
        product_id: Optional[int] = None,
        raw_material_id: Optional[int] = None,
        stage_id: Optional[int] = None,
        style: Optional[str] = None,
        colour: Optional[str] = None,
    ) -> dict:
        words = search_words(search)

        def _find(db: Session) -> dict:
            query = _enriched_query()
            if product_id is not None:
                query = query.where(BOMLine.product_id == product_id)
            if raw_material_id is not None:
                query = query.where(BOMLine.raw_material_id == raw_material_id)
            if stage_id is not None:
                query = query.where(BOMLine.stage_id == stage_id)
            if style is not None:
                query = query.where(BOMLine.style == style)
            if colour is not None:
                query = query.where(BOMLine.colour == colour)
            for word in words:
                pattern = f"%{word}%"
                query = query.where(
                    or_(
                        RawMaterial.name.ilike(pattern),
                        BOMLine.style.ilike(pattern),
                        BOMLine.colour.ilike(pattern),
                    )
                )
            query = query.order_by(
                BOMLine.product_id, BOMLine.stage_id, BOMLine.style, BOMLine.colour, BOMLine.id
            )
            rows, total = paginate_multi(db, query, page, page_size)
            items = [_row_to_response(r) for r in rows]
            return build_paginated_response(items, total, page, page_size)

        return await run_db(_find)

    @staticmethod
    async def get_variants(product_id: int) -> List[BOMVariantResponse]:
        """Distinct style x colour combos a product has a BOM for (variant picker)."""
        def _get(db: Session) -> List[BOMVariantResponse]:
            rows = db.execute(
                select(BOMLine.style, BOMLine.colour)
                .where(BOMLine.product_id == product_id, BOMLine.deleted_at.is_(None))
                .distinct()
                .order_by(BOMLine.style, BOMLine.colour)
            ).all()
            return [BOMVariantResponse(style=s, colour=c) for (s, c) in rows]

        return await run_db(_get)

    @staticmethod
    async def get_production_calc(
        product_id: int,
        quantity: int,
        style: Optional[str] = None,
        colour: Optional[str] = None,
    ) -> ProductionCalcResponse:
        """Material requirements + shortage for producing `quantity` units of a variant.
        Aggregates per raw material (summing duplicate BOM lines)."""
        def _calc(db: Session) -> ProductionCalcResponse:
            product = db.execute(
                select(Product).where(
                    Product.id == product_id, Product.deleted_at.is_(None)
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
            if style is not None:
                bom_query = bom_query.where(BOMLine.style == style)
            if colour is not None:
                bom_query = bom_query.where(BOMLine.colour == colour)
            rows = db.execute(bom_query.order_by(BOMLine.raw_material_id)).all()

            # Aggregate by raw material — a material can appear on several lines (sum them).
            by_rm: dict[int, tuple[Decimal, RawMaterial]] = {}
            for line, raw in rows:
                per_unit = _per_unit(line.qty_per_batch, line.batch_size) or Decimal("0")
                total_needed = per_unit * quantity
                if raw.id in by_rm:
                    prev, _ = by_rm[raw.id]
                    by_rm[raw.id] = (prev + total_needed, raw)
                else:
                    by_rm[raw.id] = (total_needed, raw)

            lines: List[ProductionCalcLineResponse] = []
            total_order_cost = Decimal("0")
            max_producible = float("inf")

            for _, (needed_qty, raw) in by_rm.items():
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
                style=style,
                colour=colour,
                quantity=quantity,
                lines=lines,
                total_order_cost=total_order_cost,
                max_producible_units=int(max_producible),
            )

        return await run_db(_calc)

    @staticmethod
    async def find_one(line_id: int) -> BOMLineResponse:
        def _find(db: Session) -> BOMLineResponse:
            row = db.execute(
                _enriched_query().where(BOMLine.id == line_id)
            ).first()
            if not row:
                raise NotFoundError("BOMLine", line_id)
            return _row_to_response(row)

        return await run_db(_find)

    @staticmethod
    async def update(line_id: int, dto: BOMLineUpdateDto) -> BOMLineResponse:
        def _update(db: Session) -> BOMLineResponse:
            row = db.execute(
                select(BOMLine).where(
                    BOMLine.id == line_id, BOMLine.deleted_at.is_(None)
                )
            ).scalar_one_or_none()
            if not row:
                raise NotFoundError("BOMLine", line_id)

            data = dto.model_dump(exclude_unset=True)
            if "product_id" in data and data["product_id"] is not None:
                _require_product(db, data["product_id"])
            if "raw_material_id" in data and data["raw_material_id"] is not None:
                _require_raw_material(db, data["raw_material_id"])
            if "stage_id" in data and data["stage_id"] is not None:
                _require_stage(db, data["stage_id"])

            text_fields = ("style", "colour")
            for k, v in data.items():
                if k in text_fields and isinstance(v, str):
                    v = normalize_unicode(v) or v
                setattr(row, k, v)
            row.updated_at = datetime.utcnow()
            db.flush()

            return _row_to_response(
                db.execute(_enriched_query().where(BOMLine.id == line_id)).first()
            )

        return await run_db(_update)

    @staticmethod
    async def remove(line_id: int) -> None:
        def _remove(db: Session) -> None:
            row = db.execute(
                select(BOMLine).where(BOMLine.id == line_id)
            ).scalar_one_or_none()
            if not row:
                raise NotFoundError("BOMLine", line_id)
            row.deleted_at = datetime.utcnow()
            db.flush()

        await run_db(_remove)
