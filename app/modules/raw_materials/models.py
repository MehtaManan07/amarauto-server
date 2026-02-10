"""
Raw material model. Schema inferred from data/raw-materials.csv.
"""

from sqlalchemy import String, Numeric, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from decimal import Decimal

from app.core.db.base import BaseModel


class RawMaterial(BaseModel):
    """
    Raw material / inventory item.
    Name is unique. Stock and min levels for check-stock.
    """

    __tablename__ = "raw_materials"

    name: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    unit_type: Mapped[str] = mapped_column(String(50), nullable=False)
    material_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    group: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    min_stock_req: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2), nullable=True
    )
    min_order_qty: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2), nullable=True
    )
    stock_qty: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=0, server_default="0"
    )
    gst: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    hsn: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    purchase_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2), nullable=True
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    treat_as_consume: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
