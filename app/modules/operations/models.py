"""
Operation model (was job_rates) - one paid, piece-rate operation for a product.

The operation_code encodes structure:  <PRODUCT> + <COMPONENT?> + <SEQUENCE?> + <SIDE? L/R/F>
e.g. AS1-B5L = product AS01, component B (seat), sequence 5, side L.
Parsed/loaded by scripts/import_operations.py (v3 combined resolver).

- stage_id is nullable: stage is NOT in the code, it is guessed from the Gujarati
  operation name or assigned later in the recipe editor.
- rate is nullable: a few ops have missing/zero rates (client fills in-app).
- sequence is nullable: some ops are named with no sequence (e.g. AS1-EL, AS1-W).
"""

from sqlalchemy import String, Numeric, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from decimal import Decimal

from app.core.db.base import BaseModel


class Operation(BaseModel):
    """A paid operation: who does what work, on which product/stage, at what rate."""

    __tablename__ = "operations"

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stage_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("stages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    sequence: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    component: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    side: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)  # L / R / F


# Operation status values for the inbox staging row.
PENDING = "pending"
PENDING_RESOLVED = "resolved"
PENDING_IGNORED = "ignored"


class PendingOperation(BaseModel):
    """
    An operation from job-list.csv that did NOT auto-resolve to a product (124 of 288).

    Staged here instead of in `operations` so that table stays clean (every row valid).
    Surfaced in the UI as an "Operations Inbox" worklist; the admin resolves each by
    attaching/creating a product or mapping it as an assembly component, at which point a
    real `operations` row is created and `resolved_op_id` is set.

    The two buckets: 91 ops across 8 Cushport assembly parts (need parent map) + 33 ops
    referencing 14 products missing from products.csv.
    """

    __tablename__ = "pending_operations"

    raw_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    raw_product_col: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    component: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    sequence: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    side: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    guessed_stage_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("stages.id", ondelete="SET NULL"), nullable=True
    )
    suggested_part: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=PENDING, server_default=PENDING, index=True
    )
    resolved_op_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("operations.id", ondelete="SET NULL"), nullable=True
    )
