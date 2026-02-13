"""
Work log DTOs.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date
from decimal import Decimal


class WorkLogCreateDto(BaseModel):
    user_id: int
    job_rate_id: int
    work_date: date
    quantity: Decimal = Field(..., ge=0)
    duration_minutes: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = Field(None, max_length=2000)

    class Config:
        from_attributes = True


class WorkLogUpdateDto(BaseModel):
    user_id: Optional[int] = None
    job_rate_id: Optional[int] = None
    work_date: Optional[date] = None
    quantity: Optional[Decimal] = Field(None, ge=0)
    duration_minutes: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = Field(None, max_length=2000)

    class Config:
        from_attributes = True


class WorkLogResponse(BaseModel):
    id: int
    user_id: int
    user_name: Optional[str] = None
    job_rate_id: int
    product_id: Optional[int] = None
    product_part_no: Optional[str] = None
    product_name: Optional[str] = None
    operation_code: Optional[str] = None
    operation_name: Optional[str] = None
    rate: Decimal
    quantity: Decimal
    total_amount: Decimal
    work_date: date
    duration_minutes: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkLogPaginatedResponse(BaseModel):
    """Paginated response for work logs list."""

    items: list[WorkLogResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_more: bool

    class Config:
        from_attributes = True
