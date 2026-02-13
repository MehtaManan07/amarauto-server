"""
Party model - customers (sundry debtors) / contact directory.
Schema inferred from data/parties.csv.
"""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional

from app.core.db.base import BaseModel


class Party(BaseModel):
    """
    Party (customer/debtor) - business Amar Automobiles sells to.
    Name is unique. Supports sundry debtors; party_type allows future sundry creditors.
    """

    __tablename__ = "parties"

    name: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    party_type: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True
    )
    address_line_1: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    address_line_2: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    address_line_3: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    address_line_4: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    address_line_5: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    pin_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    fax: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    contact_person: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mobile: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    gstin: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
