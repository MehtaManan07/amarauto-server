from datetime import datetime
from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from typing import Optional
import uuid


class Base(DeclarativeBase):
    """Base class for all database models"""

    pass


class BaseModel(Base):
    """
    Abstract base model that provides common fields for all entities.
    Similar to TypeORM's BaseEntity but with SQLAlchemy 2.0 style.
    """

    __abstract__ = True

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False), nullable=True, default=None
    )
