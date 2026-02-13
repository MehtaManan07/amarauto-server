"""
Job rate (operation) DTOs.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from decimal import Decimal


class JobRateCreateDto(BaseModel):
    product_id: int
    operation_code: str = Field(..., max_length=50)
    operation_name: str = Field(..., max_length=255)
    rate: Decimal = Field(..., ge=0)
    sequence: int = Field(default=0, ge=0)

    class Config:
        from_attributes = True


class JobRateUpdateDto(BaseModel):
    product_id: Optional[int] = None
    operation_code: Optional[str] = Field(None, max_length=50)
    operation_name: Optional[str] = Field(None, max_length=255)
    rate: Optional[Decimal] = Field(None, ge=0)
    sequence: Optional[int] = Field(None, ge=0)

    class Config:
        from_attributes = True


class JobRateResponse(BaseModel):
    id: int
    product_id: int
    product_part_no: Optional[str] = None
    operation_code: str
    operation_name: str
    rate: Decimal
    sequence: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
