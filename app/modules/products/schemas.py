"""
Product DTOs. BOM lines placeholder for get BOM (filled when BOM module exists).
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime
from decimal import Decimal


class ProductCreateDto(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    category: Optional[str] = Field(None, max_length=255)
    group: Optional[str] = Field(None, max_length=255)
    mrp: Optional[Decimal] = Field(None, ge=0)
    qty: Optional[Decimal] = Field(None, ge=0)
    gst: Optional[str] = Field(None, max_length=20)
    hsn: Optional[str] = Field(None, max_length=20)
    part_no: str = Field(..., min_length=1, max_length=100)
    model_name: Optional[str] = Field(None, max_length=255)
    is_active: bool = True
    product_image: Optional[str] = Field(None, max_length=512)
    distributor_price: Optional[Decimal] = Field(None, ge=0)
    dealer_price: Optional[Decimal] = Field(None, ge=0)
    retail_price: Optional[Decimal] = Field(None, ge=0)
    unit_of_measure: Optional[str] = Field(None, max_length=50)

    class Config:
        from_attributes = True


class ProductUpdateDto(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    category: Optional[str] = Field(None, max_length=255)
    group: Optional[str] = Field(None, max_length=255)
    mrp: Optional[Decimal] = Field(None, ge=0)
    qty: Optional[Decimal] = Field(None, ge=0)
    gst: Optional[str] = Field(None, max_length=20)
    hsn: Optional[str] = Field(None, max_length=20)
    part_no: Optional[str] = Field(None, min_length=1, max_length=100)
    model_name: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None
    product_image: Optional[str] = Field(None, max_length=512)
    distributor_price: Optional[Decimal] = Field(None, ge=0)
    dealer_price: Optional[Decimal] = Field(None, ge=0)
    retail_price: Optional[Decimal] = Field(None, ge=0)
    unit_of_measure: Optional[str] = Field(None, max_length=50)

    class Config:
        from_attributes = True


class ProductResponse(BaseModel):
    id: int
    name: str
    category: Optional[str] = None
    group: Optional[str] = None
    mrp: Optional[Decimal] = None
    qty: Optional[Decimal] = None
    gst: Optional[str] = None
    hsn: Optional[str] = None
    part_no: str
    model_name: Optional[str] = None
    is_active: bool
    product_image: Optional[str] = None
    distributor_price: Optional[Decimal] = None
    dealer_price: Optional[Decimal] = None
    retail_price: Optional[Decimal] = None
    unit_of_measure: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BOMLineResponse(BaseModel):
    """Single BOM line (raw material + qty). Filled by BOM module later."""
    raw_material_id: Optional[int] = None
    raw_material_name: Optional[str] = None
    variant: Optional[str] = None
    batch_qty: Optional[Decimal] = None
    raw_qty: Optional[Decimal] = None

    class Config:
        from_attributes = True


class ProductDetailResponse(ProductResponse):
    """Product with BOM. bom populated when BOM module exists."""
    bom: List[BOMLineResponse] = []

    class Config:
        from_attributes = True


class BulkItemResult(BaseModel):
    """Result for one item in a bulk create."""
    index: int = Field(..., description="1-based index in the request list")
    status: str = Field(..., description="ok | skip | error")
    part_no: Optional[str] = None
    message: str = Field(..., description="e.g. product name for ok, reason for skip/error")


class BulkCreateResponse(BaseModel):
    """Response for bulk product create."""
    added: int = 0
    skipped: int = 0
    errors: int = 0
    details: List[BulkItemResult] = Field(default_factory=list)
