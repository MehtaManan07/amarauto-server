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
