"""
Work log model - a piece-rate labor record: a worker did `quantity` of an operation.

Anchored on `operation_id` (which resolves product, component, stage, sequence, side, rate).
`rate` and `total_amount` are SNAPSHOTS at create time so later rate changes never rewrite
payroll. batch_id/stage_id tie the labor to a production batch when known (defaulted in UI),
but a work log can also stand alone (operation + worker + qty + date is the minimum).
"""

from sqlalchemy import Date, Numeric, Integer, String, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from decimal import Decimal
from datetime import date

from app.core.db.base import BaseModel


class WorkLog(BaseModel):
    """One labor entry. Pay = quantity * rate (snapshotted)."""

    __tablename__ = "work_logs"

    worker_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    operation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("operations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    batch_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("batches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    stage_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("stages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    variant: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)  # HH:MM
    end_time: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)  # HH:MM
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
