import enum
from sqlalchemy import String, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional

from app.core.db.base import BaseModel


class Role(str, enum.Enum):
    """User role enum"""

    ADMIN = "Admin"
    SUPERVISOR = "Supervisor"
    STAFF = "Staff"
    WORKER = "Worker"


class Status(str, enum.Enum):
    """User status enum"""

    ACTIVE = "Active"
    INACTIVE = "Inactive"


class User(BaseModel):
    """
    User model - equivalent to TypeORM User entity.
    Extends BaseModel which provides: id, created_at, updated_at, deleted_at
    """

    __tablename__ = "users"

    username: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )

    password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        # Note: In SQLAlchemy, "select: false" behavior is typically handled
        # at the query level using deferred() or by explicitly selecting columns
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    role: Mapped[Role] = mapped_column(
        SQLEnum(
            Role,
            name="users_role_enum",
            native_enum=False,
        ),
        nullable=False,
        default=Role.WORKER,
        server_default=Role.WORKER.value,
    )

    phone: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, default=None
    )

    job: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        default=None,
        comment="Brief description of work (e.g., Cutting, Stitching, Finishing, Stock Management)",
    )

    status: Mapped[Status] = mapped_column(
        SQLEnum(
            Status,
            name="users_status_enum",
            native_enum=False,
        ),
        nullable=False,
        default=Status.ACTIVE,
        server_default=Status.ACTIVE.value,
    )

