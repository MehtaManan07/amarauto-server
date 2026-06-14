"""
Production execution models — the batch flow and its immutable ledgers.

WIP is DERIVED from these ledgers, never stored as a counter:
    waiting(batch, stage) = received(moved in) - rejected - moved_out

- Batch: a tracked lot of one product/variant flowing through the stages.
- BatchMovement: append-only ledger of qty moving into a stage (from_stage NULL = intake).
- BatchReject: scrap recorded at a stage (qty can shrink between stages).
- MaterialConsumption: raw material consumed by a batch at a stage (on intake/move).
  Was `inventory_logs` for the production path; stock balance still lives on raw_materials.
"""

from sqlalchemy import String, Numeric, Integer, ForeignKey, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from decimal import Decimal
from datetime import datetime

from app.core.db.base import BaseModel


# Batch status values (kept as plain strings, not a DB enum, for easy edits).
BATCH_OPEN = "open"           # created, not yet advanced past first stage
BATCH_IN_PROGRESS = "in_progress"
BATCH_DONE = "done"
BATCH_CANCELLED = "cancelled"


class Batch(BaseModel):
    """A tracked production lot. batch_no is human-facing and unique."""

    __tablename__ = "batches"

    batch_no: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    style: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    colour: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=BATCH_OPEN, server_default=BATCH_OPEN, index=True
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )


class BatchMovement(BaseModel):
    """Append-only: `quantity` units of a batch moved into `to_stage_id`.

    from_stage_id NULL means intake (qty entering the flow at the first stage).
    """

    __tablename__ = "batch_movements"

    batch_id: Mapped[int] = mapped_column(
        ForeignKey("batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_stage_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("stages.id", ondelete="SET NULL"), nullable=True
    )
    to_stage_id: Mapped[int] = mapped_column(
        ForeignKey("stages.id", ondelete="SET NULL"), nullable=False, index=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    moved_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    moved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=False
    )


class BatchReject(BaseModel):
    """Scrap recorded for a batch at a stage."""

    __tablename__ = "batch_rejects"

    batch_id: Mapped[int] = mapped_column(
        ForeignKey("batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage_id: Mapped[int] = mapped_column(
        ForeignKey("stages.id", ondelete="SET NULL"), nullable=False, index=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class MaterialConsumption(BaseModel):
    """Raw material consumed by a batch at a stage. Snapshots stock before/after for audit."""

    __tablename__ = "material_consumption"

    batch_id: Mapped[int] = mapped_column(
        ForeignKey("batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("stages.id", ondelete="SET NULL"), nullable=True, index=True
    )
    raw_material_id: Mapped[int] = mapped_column(
        ForeignKey("raw_materials.id", ondelete="CASCADE"), nullable=False, index=True
    )
    qty_consumed: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    previous_qty: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    new_qty: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
