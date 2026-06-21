"""
BOM line DTOs (new production-flow schema).

A BOM line = one raw-material requirement for a product, at a stage, for a 2-D variant
(style x colour). Quantity basis: per_unit = qty_per_batch / batch_size.

IMPORTANT: duplicate lines (same product+stage+style+colour+material) are REAL — they are
SUMMED, never deduped. Two rows = two cut pieces (e.g. main panel + trim). So create never
merges; each call adds a distinct line.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from decimal import Decimal


class BOMLineCreateDto(BaseModel):
    product_id: int = Field(..., gt=0)
    raw_material_id: int = Field(..., gt=0)
    stage_id: Optional[int] = Field(None, gt=0)
    style: Optional[str] = Field(None, max_length=100)
    colour: Optional[str] = Field(None, max_length=100)
    batch_size: Decimal = Field(default=Decimal("1"), gt=0, description="Recipe batch (QTY); divisor for per-unit")
    qty_per_batch: Decimal = Field(..., ge=0, description="Total raw material for one batch")

    class Config:
        from_attributes = True


class BOMLineUpdateDto(BaseModel):
    product_id: Optional[int] = Field(None, gt=0)
    raw_material_id: Optional[int] = Field(None, gt=0)
    stage_id: Optional[int] = Field(None, gt=0)
    style: Optional[str] = Field(None, max_length=100)
    colour: Optional[str] = Field(None, max_length=100)
    batch_size: Optional[Decimal] = Field(None, gt=0)
    qty_per_batch: Optional[Decimal] = Field(None, ge=0)

    class Config:
        from_attributes = True


class BOMLineResponse(BaseModel):
    id: int
    product_id: int
    stage_id: Optional[int] = None
    raw_material_id: int
    style: Optional[str] = None
    colour: Optional[str] = None
    batch_size: Decimal
    qty_per_batch: Decimal
    per_unit: Optional[Decimal] = None  # qty_per_batch / batch_size
    # Enriched for display (recipe editor): not stored on the row.
    product_name: Optional[str] = None
    product_part_no: Optional[str] = None
    raw_material_name: Optional[str] = None
    raw_material_unit: Optional[str] = None
    stage_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BOMPaginatedResponse(BaseModel):
    """Paginated response for BOM lines list."""

    items: list[BOMLineResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_more: bool

    class Config:
        from_attributes = True


class BOMVariantResponse(BaseModel):
    """A distinct style x colour combo a product has a recipe for."""

    style: Optional[str] = None
    colour: Optional[str] = None


class ProductionCalcLineResponse(BaseModel):
    """Single line in production calculator result (aggregated per raw material)."""

    raw_material_name: str
    unit_type: str
    needed_qty: Decimal
    current_stock: Decimal
    shortage: Decimal
    status: str  # "ok" | "low"
    purchase_price: Optional[Decimal] = None
    order_cost: Decimal


class ProductionCalcResponse(BaseModel):
    """Production calculator response: material needs + shortage for N units of a variant."""

    product_part_no: str
    product_name: str
    style: Optional[str] = None
    colour: Optional[str] = None
    quantity: int
    lines: list[ProductionCalcLineResponse]
    total_order_cost: Decimal
    max_producible_units: int
