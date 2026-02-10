"""
Product model. Schema inferred from data/products.csv.
part_no is unique.
"""

from sqlalchemy import String, Numeric, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from decimal import Decimal

from app.core.db.base import BaseModel


class Product(BaseModel):
    """
    Finished product / SKU. part_no is unique.
    BOM and operations (job rates) reference products.
    """

    __tablename__ = "products"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    category: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    group: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mrp: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    qty: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    gst: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    hsn: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    part_no: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    product_image: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    distributor_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2), nullable=True
    )
    dealer_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2), nullable=True
    )
    retail_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2), nullable=True
    )
    unit_of_measure: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
