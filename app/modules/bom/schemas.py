"""
BOM line DTOs.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from decimal import Decimal


class BOMLineCreateDto(BaseModel):
    product_id: int
    raw_material_id: int
    variant: Optional[str] = Field(None, max_length=100)
    batch_qty: Decimal = Field(default=Decimal("1"), ge=0)
    raw_qty: Decimal = Field(..., ge=0)

    class Config:
        from_attributes = True


class BOMLineUpdateDto(BaseModel):
    product_id: Optional[int] = None
    raw_material_id: Optional[int] = None
    variant: Optional[str] = Field(None, max_length=100)
    batch_qty: Optional[Decimal] = Field(None, ge=0)
    raw_qty: Optional[Decimal] = Field(None, ge=0)

    class Config:
        from_attributes = True


class ProductionCalcLineResponse(BaseModel):
    """Single line in production calculator result."""

    raw_material_name: str
    unit_type: str
    needed_qty: Decimal
    current_stock: Decimal
    shortage: Decimal
    status: str  # "ok" | "low"
    purchase_price: Optional[Decimal] = None
    order_cost: Decimal


class ProductionCalcResponse(BaseModel):
    """Production calculator response."""

    product_part_no: str
    product_name: str
    variant: Optional[str] = None
    quantity: int
    lines: list[ProductionCalcLineResponse]
    total_order_cost: Decimal
    max_producible_units: int


class BOMLineResponse(BaseModel):
    id: int
    product_id: int
    raw_material_id: int
    product_name: Optional[str] = None
    product_part_no: Optional[str] = None
    raw_material_name: Optional[str] = None
    variant: Optional[str] = None
    batch_qty: Decimal
    raw_qty: Decimal
    created_at: datetime
    updated_at: datetime


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
