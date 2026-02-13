"""Inventory log schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class InventoryLogResponse(BaseModel):
    """Inventory log entry for API response."""

    id: int
    raw_material_id: int
    user_id: Optional[int] = None
    type: str
    quantity_delta: Decimal
    previous_qty: Decimal
    new_qty: Decimal
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AdjustStockRequest(BaseModel):
    """Request body for adjust-stock endpoint."""

    quantity_delta: Decimal
    notes: Optional[str] = None
