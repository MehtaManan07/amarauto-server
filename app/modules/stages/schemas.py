"""
Stage DTOs. Stages are config (cutting/stitching/finishing/assembly), ordered by sequence.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class StageCreateDto(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    sequence: int = Field(..., ge=1)
    is_active: bool = True

    class Config:
        from_attributes = True


class StageUpdateDto(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    sequence: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None

    class Config:
        from_attributes = True


class StageResponse(BaseModel):
    id: int
    name: str
    sequence: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True
