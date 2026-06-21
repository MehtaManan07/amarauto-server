"""
Stage model - an ordered step in the production flow.

Seeded (see baseline migration): cutting(1), stitching(2), finishing(3), assembly(4).
Stages are config; a product's actual path is derived from its recipe (BOM/operations),
never hardcoded — many products skip stitching (cutting -> finishing only).
"""

from sqlalchemy import String, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseModel


class Stage(BaseModel):
    """One production stage. `sequence` orders stages globally (1 = first)."""

    __tablename__ = "stages"

    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
