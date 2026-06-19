"""
Batch (production execution) DTOs.

A batch is a tracked lot of one product/variant flowing through the stages. WIP is DERIVED
from the immutable ledgers, never stored:  waiting(stage) = moved_in - moved_out - rejected.

14a scope: batch create (+ intake movement), list/get, per-stage WIP. Advance/consume (14b)
and rejects (14c) come next.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


class BatchCreateDto(BaseModel):
    product_id: int = Field(..., gt=0)
    quantity: Decimal = Field(..., gt=0)
    style: Optional[str] = Field(None, max_length=100)
    colour: Optional[str] = Field(None, max_length=100)
    # Omit batch_no to auto-generate (B-0001...). start_stage_id defaults to the first stage.
    batch_no: Optional[str] = Field(None, max_length=50)
    start_stage_id: Optional[int] = Field(None, gt=0)

    class Config:
        from_attributes = True


class BatchUpdateDto(BaseModel):
    """Light edits only — quantities flow through movements/rejects, not direct edits."""
    style: Optional[str] = Field(None, max_length=100)
    colour: Optional[str] = Field(None, max_length=100)
    status: Optional[str] = Field(None, max_length=20)

    class Config:
        from_attributes = True


class BatchWipLine(BaseModel):
    """Units currently waiting at a stage for this batch (derived from ledgers)."""
    stage_id: int
    stage_name: str
    sequence: int
    waiting: Decimal


class BatchResponse(BaseModel):
    id: int
    batch_no: str
    product_id: int
    product_part_no: Optional[str] = None
    product_name: Optional[str] = None
    style: Optional[str] = None
    colour: Optional[str] = None
    quantity: Decimal
    status: str
    # Derived: where the units currently sit (highest-sequence stage with waiting > 0).
    current_stage_id: Optional[int] = None
    current_stage_name: Optional[str] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BatchDetailResponse(BatchResponse):
    """Batch + full per-stage WIP breakdown."""
    wip: List[BatchWipLine] = Field(default_factory=list)


class BatchPaginatedResponse(BaseModel):
    items: List[BatchResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_more: bool

    class Config:
        from_attributes = True
