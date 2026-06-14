"""
BOM (Bill of Materials) line model. Links a product+stage+variant to a raw material
with the per-batch quantity needed. Source: new-data/bom.csv.

Quantity basis (proven from data):
    per_unit_consumption = qty_per_batch / batch_size
    consumption for N units = qty_per_batch * N / batch_size
`batch_size` is the recipe's standard batch (the CSV QTY col, constant within a product);
`qty_per_batch` is the total raw material for one such batch.

IMPORTANT: duplicate lines (same product+stage+style+colour+material) are REAL — SUM them,
do not dedup. Two rows = two cut pieces (e.g. main panel 9.22m + trim 1.66m).
"""

from sqlalchemy import String, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
from decimal import Decimal

from app.core.db.base import BaseModel


class BOMLine(BaseModel):
    """One material requirement for a product at a given stage and variant."""

    __tablename__ = "bom_lines"

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
    raw_material_id: Mapped[int] = mapped_column(
        ForeignKey("raw_materials.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Variant is 2-D: style (texture, e.g. PUNCH/PLAIN) x colour (BLACK/BEIGE/...).
    style: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    colour: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    batch_size: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=1, server_default="1"
    )
    qty_per_batch: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)

    product: Mapped["Product"] = relationship("Product", foreign_keys=[product_id])
    raw_material: Mapped["RawMaterial"] = relationship(
        "RawMaterial", foreign_keys=[raw_material_id]
    )
