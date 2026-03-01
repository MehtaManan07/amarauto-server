"""
Stage inventory model - tracks WIP quantities at each production stage.
"""

from sqlalchemy import String, Numeric, Integer, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from decimal import Decimal

from app.core.db.base import BaseModel


class StageInventory(BaseModel):
    """
    WIP quantity at a stage for a product/variant.
    One row per (product_id, variant, stage_number) - quantity is aggregated.
    """

    __tablename__ = "stage_inventory"
    __table_args__ = (
        Index("ix_stage_inv_lookup", "product_id", "stage_number", "variant"),
    )

    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    variant: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    stage_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
