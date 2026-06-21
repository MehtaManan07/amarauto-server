"""
Product model. Schema inferred from data/products.csv.
part_no is unique.
"""

from sqlalchemy import String, Numeric, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from decimal import Decimal

from app.core.db.base import BaseModel


class Product(BaseModel):
    """
    Finished product / SKU. part_no is unique.
    BOM and operations reference products.

    is_manufactured: this product is made in-house (has a recipe / runs through stages).
                     Most products are catalog-only (sellable, not made) -> False.
    is_component:    this product is a sub-part of an assembly (e.g. Cushport seat/head-rest)
                     rather than a standalone SKU. See product_components.
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
    is_manufactured: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    is_component: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
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


class ProductComponent(BaseModel):
    """
    Assembly structure: `parent_id` is made up of `qty_per_parent` units of `component_id`.

    e.g. a Cushport (parent) = 1 seat + 1 head-rest + 1 neck-pillow (components), where each
    component is itself a Product (is_component=True) that runs its own cutting/stitching/
    finishing as a separate batch, then combines in the assembly stage.
    """

    __tablename__ = "product_components"

    parent_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    component_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    qty_per_parent: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=1, server_default="1"
    )
