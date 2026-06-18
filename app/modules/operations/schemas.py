"""
Operation DTOs. An operation is one paid, piece-rate unit of work for a product
at a stage. `code` is its identity (worklog resolution key); stage/rate/sequence/
component/side are nullable because the source data is incomplete (client fills in-app).
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
from decimal import Decimal


SIDES = ("L", "R", "F")


def _normalize_side(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    v = v.strip().upper()
    if v == "":
        return None
    if v not in SIDES:
        raise ValueError(f"side must be one of {', '.join(SIDES)}")
    return v


class OperationCreateDto(BaseModel):
    # product_id is optional: omit it to create an UNMAPPED op (product assigned later).
    product_id: Optional[int] = Field(None, gt=0)
    stage_id: Optional[int] = Field(None, gt=0)
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=255)
    rate: Optional[Decimal] = Field(None, ge=0)
    sequence: Optional[int] = Field(None, ge=0)
    component: Optional[str] = Field(None, max_length=50)
    side: Optional[str] = Field(None, max_length=5, description="L / R / F")
    product_hint: Optional[str] = Field(None, max_length=255, description="Raw product text for unmapped ops")

    _side = field_validator("side")(_normalize_side)

    class Config:
        from_attributes = True


class OperationUpdateDto(BaseModel):
    product_id: Optional[int] = Field(None, gt=0)
    stage_id: Optional[int] = Field(None, gt=0)
    code: Optional[str] = Field(None, min_length=1, max_length=50)
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    rate: Optional[Decimal] = Field(None, ge=0)
    sequence: Optional[int] = Field(None, ge=0)
    component: Optional[str] = Field(None, max_length=50)
    side: Optional[str] = Field(None, max_length=5, description="L / R / F")
    product_hint: Optional[str] = Field(None, max_length=255)

    _side = field_validator("side")(_normalize_side)

    class Config:
        from_attributes = True


class OperationResponse(BaseModel):
    id: int
    product_id: Optional[int] = None  # NULL == unmapped
    stage_id: Optional[int] = None
    code: str
    name: str
    rate: Optional[Decimal] = None
    sequence: Optional[int] = None
    component: Optional[str] = None
    side: Optional[str] = None
    product_hint: Optional[str] = None
    # Enriched for display (recipe editor / worklog): not stored on the row.
    product_part_no: Optional[str] = None
    stage_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class OperationPaginatedResponse(BaseModel):
    """Paginated response for operations list."""

    items: list[OperationResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_more: bool

    class Config:
        from_attributes = True
