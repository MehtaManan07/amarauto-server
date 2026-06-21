"""
Work log DTOs (new schema). A work log is a piece-rate labor record anchored on an
operation: worker did `quantity` of operation X on a date. rate + total_amount are
SNAPSHOTTED at create (rate defaults to the operation's rate, overridable). batch_id/
stage_id/variant tie it to a production batch when known (all optional). Times optional.

Payroll = sum(total_amount) per worker over a date range.
"""

import re
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal

TIME_PATTERN = re.compile(r"^\d{1,2}:\d{2}$")


def _parse_time_to_minutes(s: str) -> int:
    if not TIME_PATTERN.match(s):
        raise ValueError("Invalid time format, use HH:MM")
    h, m = (int(p) for p in s.split(":"))
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError("Invalid time")
    return h * 60 + m


def compute_duration_minutes(start: str, end: str) -> int:
    start_m, end_m = _parse_time_to_minutes(start), _parse_time_to_minutes(end)
    if end_m <= start_m:
        raise ValueError("end_time must be after start_time")
    return end_m - start_m


def _validate_optional_time(v: Optional[str]) -> Optional[str]:
    if v is None or v == "":
        return None
    if not TIME_PATTERN.match(v):
        raise ValueError("Use HH:MM format (e.g. 09:30)")
    h, m = (int(p) for p in v.split(":"))
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError("Invalid time")
    return v


class _WorkLogFields(BaseModel):
    """Shared fields for create + bulk item (worker_id is set separately on bulk)."""
    operation_id: int = Field(..., gt=0)
    quantity: Decimal = Field(..., gt=0)
    work_date: date
    rate: Optional[Decimal] = Field(None, ge=0, description="Override; defaults to the operation's rate")
    batch_id: Optional[int] = Field(None, gt=0)
    stage_id: Optional[int] = Field(None, gt=0, description="Defaults to the operation's stage")
    variant: Optional[str] = Field(None, max_length=100)
    start_time: Optional[str] = Field(None, description="HH:MM")
    end_time: Optional[str] = Field(None, description="HH:MM")
    notes: Optional[str] = Field(None, max_length=2000)

    @field_validator("start_time", "end_time")
    @classmethod
    def _times(cls, v):
        return _validate_optional_time(v)

    @model_validator(mode="after")
    def _end_after_start(self):
        if self.start_time and self.end_time:
            compute_duration_minutes(self.start_time, self.end_time)
        return self

    class Config:
        from_attributes = True


class WorkLogCreateDto(_WorkLogFields):
    worker_id: int = Field(..., gt=0)


class WorkLogBulkItemDto(_WorkLogFields):
    """One entry in a bulk create (worker_id comes from the wrapper)."""
    pass


class WorkLogBulkCreateDto(BaseModel):
    """Bulk entry for ONE worker — matches the worklog grid (grouped by worker)."""
    worker_id: int = Field(..., gt=0)
    items: List[WorkLogBulkItemDto] = Field(..., min_length=1)

    class Config:
        from_attributes = True


class WorkLogUpdateDto(BaseModel):
    quantity: Optional[Decimal] = Field(None, gt=0)
    rate: Optional[Decimal] = Field(None, ge=0)
    work_date: Optional[date] = None
    batch_id: Optional[int] = Field(None, gt=0)
    stage_id: Optional[int] = Field(None, gt=0)
    variant: Optional[str] = Field(None, max_length=100)
    start_time: Optional[str] = Field(None, description="HH:MM")
    end_time: Optional[str] = Field(None, description="HH:MM")
    notes: Optional[str] = Field(None, max_length=2000)

    @field_validator("start_time", "end_time")
    @classmethod
    def _times(cls, v):
        return _validate_optional_time(v)

    @model_validator(mode="after")
    def _end_after_start(self):
        if self.start_time and self.end_time:
            compute_duration_minutes(self.start_time, self.end_time)
        return self

    class Config:
        from_attributes = True


class WorkLogResponse(BaseModel):
    id: int
    worker_id: int
    worker_name: Optional[str] = None
    operation_id: int
    operation_code: Optional[str] = None
    operation_name: Optional[str] = None
    product_id: Optional[int] = None
    product_part_no: Optional[str] = None
    batch_id: Optional[int] = None
    batch_no: Optional[str] = None
    stage_id: Optional[int] = None
    stage_name: Optional[str] = None
    variant: Optional[str] = None
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
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class WorkLogPaginatedResponse(BaseModel):
    items: List[WorkLogResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_more: bool

    class Config:
        from_attributes = True


class BulkCreateResponse(BaseModel):
    created: int = 0
    items: List[WorkLogResponse] = Field(default_factory=list)


# ----------------------------- payroll -----------------------------

class PayrollLine(BaseModel):
    worker_id: int
    worker_name: Optional[str] = None
    entries: int
    total_quantity: Decimal
    total_amount: Decimal


class PayrollResponse(BaseModel):
    from_date: date
    to_date: date
    lines: List[PayrollLine] = Field(default_factory=list)
    grand_total: Decimal
