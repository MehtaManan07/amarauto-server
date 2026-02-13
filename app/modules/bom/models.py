"""
BOM (Bill of Materials) line model. Links product to raw material with variant and quantities.
Schema inferred from data/bom-detail.csv.
"""

from sqlalchemy import String, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
from decimal import Decimal

from app.core.db.base import BaseModel


class BOMLine(BaseModel):
    """
    One BOM line: product + raw material + variant (e.g. colour) + batch_qty + raw_qty.
    Same (product, variant, raw_material) can appear multiple times (e.g. different raw_qty).
    """

    __tablename__ = "bom_lines"

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    raw_material_id: Mapped[int] = mapped_column(
        ForeignKey("raw_materials.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    variant: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    batch_qty: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=1, server_default="1"
    )
    raw_qty: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False,
    )

    product: Mapped["Product"] = relationship("Product", foreign_keys=[product_id])
    raw_material: Mapped["RawMaterial"] = relationship("RawMaterial", foreign_keys=[raw_material_id])
