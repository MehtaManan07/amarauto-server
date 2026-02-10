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


class BOMLineResponse(BaseModel):
    id: int
    product_id: int
    raw_material_id: int
    raw_material_name: Optional[str] = None
    variant: Optional[str] = None
    batch_qty: Decimal
    raw_qty: Decimal
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
