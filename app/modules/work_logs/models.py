"""
Work log model - tracks worker production: who did which operation on which product.
"""

from sqlalchemy import Date, Numeric, Integer, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from decimal import Decimal
from datetime import date

from app.core.db.base import BaseModel


class WorkLog(BaseModel):
    """
    One work log entry: worker completed quantity of operation on product on date.
    rate and total_amount are snapshots at create time for payroll accuracy.
    """

    __tablename__ = "work_logs"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_rate_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("job_rates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
