"""
Inventory log model - tracks when stock was added or removed from raw materials.
"""

import enum
from sqlalchemy import String, Numeric, Integer, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from decimal import Decimal

from app.core.db.base import BaseModel


class LogType(str, enum.Enum):
    """Type of stock change."""

    ADD = "add"
    REMOVE = "remove"
    ADJUST = "adjust"


class InventoryLog(BaseModel):
    """
    Log entry for raw material stock changes.
    Records add, remove, or adjust operations with quantity delta and notes.
    """

    __tablename__ = "inventory_logs"

    raw_material_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("raw_materials.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity_delta: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False
    )  # positive = add, negative = remove
    previous_qty: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False
    )
    new_qty: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
