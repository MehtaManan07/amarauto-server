"""
Job rate (operation) model. Links product to operation with rate and sequence.
Schema inferred from data/job-rate-list.csv.
"""

from sqlalchemy import String, Numeric, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from decimal import Decimal

from app.core.db.base import BaseModel


class JobRate(BaseModel):
    """
    One operation for a product: operation_code, operation_name, rate, sequence.
    sequence orders operations (1 = first, 2 = second, etc.) for multi-stage production.
    """

    __tablename__ = "job_rates"

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    operation_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    operation_name: Mapped[str] = mapped_column(String(255), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    sequence: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
