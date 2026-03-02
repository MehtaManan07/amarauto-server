"""
Production service - complete stages with automatic material deduction.
"""

from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from decimal import Decimal

from app.core.db.engine import run_db
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.products.models import Product
from app.modules.raw_materials.models import RawMaterial
from app.modules.inventory_logs.models import InventoryLog, LogType
from app.modules.bom.models import BOMLine
from .models import StageInventory
from .schemas import (
    StageCompletionDto,
    StageCompletionResponse,
    StageInventoryResponse,
    MaterialDeduction,
    MaterialsPreviewResponse,
    MaterialRequirement,
)


def _to_stage_inv_response(
    row: StageInventory,
    product_part_no: Optional[str] = None,
    product_name: Optional[str] = None,
) -> StageInventoryResponse:
    return StageInventoryResponse(
        id=row.id,
        product_id=row.product_id,
        product_part_no=product_part_no,
        product_name=product_name,
        variant=row.variant,
        stage_number=row.stage_number,
        quantity=row.quantity,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class ProductionService:
    @staticmethod
    async def complete_stage(
        dto: StageCompletionDto,
        user_id: Optional[int] = None,
    ) -> StageCompletionResponse:
        """
        Complete a production stage: deduct materials, deduct from previous stage if any,
        add to current stage inventory.
        """

        def _complete(db: Session) -> StageCompletionResponse:
            # 1. Validate product exists
            product = db.execute(
                select(Product).where(
                    Product.id == dto.product_id,
                    Product.deleted_at.is_(None),
                )
            ).scalar_one_or_none()
            if not product:
                raise NotFoundError("Product", dto.product_id)

            # 2. Fetch BOM lines for this product/variant/stage
            bom_query = (
                select(BOMLine, RawMaterial)
                .join(RawMaterial, BOMLine.raw_material_id == RawMaterial.id)
                .where(
                    BOMLine.product_id == dto.product_id,
                    BOMLine.stage_number == dto.stage_number,
                    BOMLine.deleted_at.is_(None),
                    RawMaterial.deleted_at.is_(None),
                )
            )
            if dto.variant:
                bom_query = bom_query.where(BOMLine.variant == dto.variant)
            else:
                bom_query = bom_query.where(BOMLine.variant.is_(None))
            bom_result = db.execute(bom_query)
            bom_rows = bom_result.all()

            # 3. If stage > 1, check previous stage has enough
            prev_stage_row = None
            if dto.stage_number > 1:
                prev_stage_query = (
                    select(StageInventory)
                    .where(
                        StageInventory.product_id == dto.product_id,
                        StageInventory.stage_number == dto.stage_number - 1,
                        StageInventory.deleted_at.is_(None),
                    )
                )
                if dto.variant:
                    prev_stage_query = prev_stage_query.where(
                        StageInventory.variant == dto.variant
                    )
                else:
                    prev_stage_query = prev_stage_query.where(
                        StageInventory.variant.is_(None)
                    )
                prev_stage_row = db.execute(prev_stage_query).scalar_one_or_none()
                prev_qty = (prev_stage_row.quantity if prev_stage_row else Decimal("0")) or Decimal(
                    "0"
                )
                if prev_qty < dto.quantity:
                    raise ConflictError(
                        f"Stage {dto.stage_number - 1} has only {prev_qty} units, "
                        f"need {dto.quantity} for stage {dto.stage_number}"
                    )

            # 4. Aggregate BOM by raw_material_id and check stock
            by_rm: dict[int, tuple[Decimal, RawMaterial]] = {}
            for line, raw in bom_rows:
                needed = (line.raw_qty / line.batch_qty) * dto.quantity
                if raw.id in by_rm:
                    prev_needed, _ = by_rm[raw.id]
                    by_rm[raw.id] = (prev_needed + needed, raw)
                else:
                    by_rm[raw.id] = (needed, raw)

            for raw_id, (needed, raw) in by_rm.items():
                current = raw.stock_qty or Decimal("0")
                if current < needed:
                    raise ConflictError(
                        f"Insufficient stock for {raw.name}: need {needed}, have {current}"
                    )

            # 5. Deduct materials and create inventory logs
            materials_deducted: List[MaterialDeduction] = []
            for raw_id, (needed, raw) in by_rm.items():
                prev_qty = raw.stock_qty or Decimal("0")
                new_qty = prev_qty - needed
                raw.stock_qty = new_qty
                log = InventoryLog(
                    raw_material_id=raw_id,
                    user_id=user_id,
                    type=LogType.REMOVE.value,
                    quantity_delta=-needed,
                    previous_qty=prev_qty,
                    new_qty=new_qty,
                    notes=f"Stage {dto.stage_number} completion for product {product.part_no}",
                )
                db.add(log)
                materials_deducted.append(
                    MaterialDeduction(
                        raw_material_id=raw_id,
                        raw_material_name=raw.name,
                        qty_deducted=needed,
                        remaining_stock=new_qty,
                    )
                )

            # 6. If stage > 1, deduct from previous stage (reuse row fetched in step 3)
            if dto.stage_number > 1 and prev_stage_row:
                prev_stage_row.quantity = (prev_stage_row.quantity or Decimal("0")) - dto.quantity
                if prev_stage_row.quantity <= 0:
                    db.delete(prev_stage_row)

            # 7. Add/update current stage inventory
            curr_query = (
                select(StageInventory)
                .where(
                    StageInventory.product_id == dto.product_id,
                    StageInventory.stage_number == dto.stage_number,
                    StageInventory.deleted_at.is_(None),
                )
            )
            if dto.variant:
                curr_query = curr_query.where(StageInventory.variant == dto.variant)
            else:
                curr_query = curr_query.where(StageInventory.variant.is_(None))
            curr_row = db.execute(curr_query).scalar_one_or_none()
            if curr_row:
                curr_row.quantity = (curr_row.quantity or Decimal("0")) + dto.quantity
                db.flush()
                db.refresh(curr_row)
                stage_inv = _to_stage_inv_response(
                    curr_row,
                    product_part_no=product.part_no,
                    product_name=product.name,
                )
            else:
                new_inv = StageInventory(
                    product_id=dto.product_id,
                    variant=dto.variant,
                    stage_number=dto.stage_number,
                    quantity=dto.quantity,
                )
                db.add(new_inv)
                db.flush()
                db.refresh(new_inv)
                stage_inv = _to_stage_inv_response(
                    new_inv,
                    product_part_no=product.part_no,
                    product_name=product.name,
                )

            return StageCompletionResponse(
                stage_inventory=stage_inv,
                materials_deducted=materials_deducted,
            )

        return await run_db(_complete)

    @staticmethod
    async def get_stage_inventory(
        product_id: Optional[int] = None,
        variant: Optional[str] = None,
        stage_number: Optional[int] = None,
    ) -> List[StageInventoryResponse]:
        """Get WIP at each stage, optionally filtered."""

        def _get(db: Session) -> List[StageInventoryResponse]:
            query = (
                select(StageInventory, Product.part_no, Product.name)
                .join(Product, StageInventory.product_id == Product.id)
                .where(
                    StageInventory.deleted_at.is_(None),
                    Product.deleted_at.is_(None),
                )
            )
            if product_id is not None:
                query = query.where(StageInventory.product_id == product_id)
            if variant is not None:
                query = query.where(StageInventory.variant == variant)
            if stage_number is not None:
                query = query.where(StageInventory.stage_number == stage_number)
            query = query.order_by(
                StageInventory.product_id,
                StageInventory.variant,
                StageInventory.stage_number,
            )
            result = db.execute(query)
            rows = result.all()
            return [
                _to_stage_inv_response(
                    row,
                    product_part_no=part_no,
                    product_name=prod_name,
                )
                for row, part_no, prod_name in rows
            ]

        return await run_db(_get)

    @staticmethod
    async def get_materials_preview(
        product_id: int,
        variant: Optional[str],
        stage_number: int,
        quantity: Decimal,
    ) -> MaterialsPreviewResponse:
        """Preview materials needed for completing a stage."""

        def _preview(db: Session) -> MaterialsPreviewResponse:
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
                    BOMLine.stage_number == stage_number,
                    BOMLine.deleted_at.is_(None),
                    RawMaterial.deleted_at.is_(None),
                )
            )
            if variant:
                bom_query = bom_query.where(BOMLine.variant == variant)
            else:
                bom_query = bom_query.where(BOMLine.variant.is_(None))
            bom_rows = db.execute(bom_query).all()

            by_rm: dict[int, tuple[Decimal, RawMaterial]] = {}
            for line, raw in bom_rows:
                needed = (line.raw_qty / line.batch_qty) * quantity
                if raw.id in by_rm:
                    prev, _ = by_rm[raw.id]
                    by_rm[raw.id] = (prev + needed, raw)
                else:
                    by_rm[raw.id] = (needed, raw)

            materials: List[MaterialRequirement] = []
            for raw_id, (needed, raw) in by_rm.items():
                current = raw.stock_qty or Decimal("0")
                shortage = max(Decimal("0"), needed - current)
                status = "ok" if shortage == 0 else "low"
                materials.append(
                    MaterialRequirement(
                        raw_material_id=raw_id,
                        raw_material_name=raw.name,
                        unit_type=raw.unit_type,
                        needed_qty=needed,
                        current_stock=current,
                        shortage=shortage,
                        status=status,
                    )
                )

            previous_stage_qty: Optional[Decimal] = None
            if stage_number > 1:
                prev_query = (
                    select(StageInventory)
                    .where(
                        StageInventory.product_id == product_id,
                        StageInventory.stage_number == stage_number - 1,
                        StageInventory.deleted_at.is_(None),
                    )
                )
                if variant:
                    prev_query = prev_query.where(
                        StageInventory.variant == variant
                    )
                else:
                    prev_query = prev_query.where(
                        StageInventory.variant.is_(None)
                    )
                prev_row = db.execute(prev_query).scalar_one_or_none()
                previous_stage_qty = (
                    prev_row.quantity if prev_row else Decimal("0")
                ) or Decimal("0")

            return MaterialsPreviewResponse(
                product_part_no=product.part_no,
                product_name=product.name,
                variant=variant,
                stage_number=stage_number,
                quantity=quantity,
                materials=materials,
                previous_stage_qty=previous_stage_qty,
            )

        return await run_db(_preview)
