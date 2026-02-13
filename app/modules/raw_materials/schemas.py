"""
RawMaterial DTOs.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from decimal import Decimal


class RawMaterialCreateDto(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    unit_type: str = Field(..., max_length=50)
    material_type: Optional[str] = Field(None, max_length=100)
    group: Optional[str] = Field(None, max_length=100)
    min_stock_req: Optional[Decimal] = Field(None, ge=0)
    min_order_qty: Optional[Decimal] = Field(None, ge=0)
    stock_qty: Decimal = Field(default=Decimal("0"), ge=0)
    gst: Optional[str] = Field(None, max_length=20)
    hsn: Optional[str] = Field(None, max_length=20)
    purchase_price: Optional[Decimal] = Field(None, ge=0)
    description: Optional[str] = None
    treat_as_consume: bool = False
    is_active: bool = True

    class Config:
        from_attributes = True


class AdjustStockRequest(BaseModel):
    """Request body for adjust-stock endpoint."""

    quantity_delta: Decimal
    notes: Optional[str] = None


class RawMaterialUpdateDto(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    unit_type: Optional[str] = Field(None, max_length=50)
    material_type: Optional[str] = Field(None, max_length=100)
    group: Optional[str] = Field(None, max_length=100)
    min_stock_req: Optional[Decimal] = Field(None, ge=0)
    min_order_qty: Optional[Decimal] = Field(None, ge=0)
    stock_qty: Optional[Decimal] = Field(None, ge=0)
    gst: Optional[str] = Field(None, max_length=20)
    hsn: Optional[str] = Field(None, max_length=20)
    purchase_price: Optional[Decimal] = Field(None, ge=0)
    description: Optional[str] = None
    treat_as_consume: Optional[bool] = None
    is_active: Optional[bool] = None

    class Config:
        from_attributes = True


class RawMaterialResponse(BaseModel):
    id: int
    name: str
    unit_type: str
    material_type: Optional[str] = None
    group: Optional[str] = None
    min_stock_req: Optional[Decimal] = None
    min_order_qty: Optional[Decimal] = None
    stock_qty: Decimal
    gst: Optional[str] = None
    hsn: Optional[str] = None
    purchase_price: Optional[Decimal] = None
    description: Optional[str] = None
    treat_as_consume: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RawMaterialPaginatedResponse(BaseModel):
    """Paginated response for raw materials list."""

    items: list[RawMaterialResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_more: bool


class StockCheckResponse(BaseModel):
    """Single item in check-stock: below min or low."""
    id: int
    name: str
    stock_qty: Decimal
    min_stock_req: Optional[Decimal]
    below_min: bool

    class Config:
        from_attributes = True


class BulkUploadItemResult(BaseModel):
    """Result for a single item in bulk upload."""
    name: str
    success: bool
    error: Optional[str] = None
    data: Optional[RawMaterialResponse] = None

    class Config:
        from_attributes = True


class BulkUploadResponse(BaseModel):
    """Overall result of bulk upload operation."""
    total: int
    success_count: int
    failure_count: int
    results: list[BulkUploadItemResult]

    class Config:
        from_attributes = True


class FieldOptionsResponse(BaseModel):
    """Unique values per field for dropdowns (e.g. unit_type, material_type, group)."""

    unit_type: Optional[list[str]] = None
    material_type: Optional[list[str]] = None
    group: Optional[list[str]] = None

    class Config:
        from_attributes = True
