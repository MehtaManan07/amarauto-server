"""
Work log DTOs.
"""

import re
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
from datetime import datetime, date
from decimal import Decimal

TIME_PATTERN = re.compile(r"^\d{1,2}:\d{2}$")


def _parse_time_to_minutes(s: str) -> int:
    """Parse HH:MM or H:MM to minutes since midnight."""
    if not TIME_PATTERN.match(s):
        raise ValueError("Invalid time format, use HH:MM")
    parts = s.split(":")
    h, m = int(parts[0]), int(parts[1])
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError("Invalid time")
    return h * 60 + m


def _compute_duration_minutes(start: str, end: str) -> int:
    """Compute duration in minutes from start_time and end_time (HH:MM)."""
    start_m = _parse_time_to_minutes(start)
    end_m = _parse_time_to_minutes(end)
    if end_m <= start_m:
        raise ValueError("end_time must be after start_time")
    return end_m - start_m


class WorkLogCreateDto(BaseModel):
    user_id: int
    job_rate_id: int
    work_date: date
    start_time: str = Field(..., description="Start time HH:MM")
    end_time: str = Field(..., description="End time HH:MM")
    quantity: Decimal = Field(..., ge=0)
    notes: Optional[str] = Field(None, max_length=2000)

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_time(cls, v: str) -> str:
        if not TIME_PATTERN.match(v):
            raise ValueError("Use HH:MM format (e.g. 09:30)")
        parts = v.split(":")
        h, m = int(parts[0]), int(parts[1])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError("Invalid time")
        return v

    @field_validator("end_time")
    @classmethod
    def end_after_start(cls, v: str, info) -> str:
        start = info.data.get("start_time")
        if start and v:
            try:
                _compute_duration_minutes(start, v)
            except ValueError as e:
                raise ValueError("end_time must be after start_time") from e
        return v

    class Config:
        from_attributes = True


class WorkLogUpdateDto(BaseModel):
    user_id: Optional[int] = None
    job_rate_id: Optional[int] = None
    work_date: Optional[date] = None
    start_time: Optional[str] = Field(None, description="Start time HH:MM")
    end_time: Optional[str] = Field(None, description="End time HH:MM")
    quantity: Optional[Decimal] = Field(None, ge=0)
    notes: Optional[str] = Field(None, max_length=2000)

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_time(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        if not TIME_PATTERN.match(v):
            raise ValueError("Use HH:MM format (e.g. 09:30)")
        parts = v.split(":")
        h, m = int(parts[0]), int(parts[1])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError("Invalid time")
        return v

    @model_validator(mode="after")
    def end_after_start(self):
        if self.start_time and self.end_time:
            try:
                _compute_duration_minutes(self.start_time, self.end_time)
            except ValueError as e:
                raise ValueError("end_time must be after start_time") from e
        return self

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
    start_time: Optional[str] = None
    end_time: Optional[str] = None
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
