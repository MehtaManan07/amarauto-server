"""raw_materials table

Revision ID: 20260210_rm
Revises: 026952705d2c
Create Date: 2026-02-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260210_rm"
down_revision: Union[str, Sequence[str], None] = "026952705d2c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "raw_materials",
        sa.Column("name", sa.String(length=255), nullable=False, unique=True),
        sa.Column("unit_type", sa.String(length=50), nullable=False),
        sa.Column("material_type", sa.String(length=100), nullable=True),
        sa.Column("group", sa.String(length=100), nullable=True),
        sa.Column("min_stock_req", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("min_order_qty", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("stock_qty", sa.Numeric(precision=15, scale=2), server_default="0", nullable=False),
        sa.Column("gst", sa.String(length=20), nullable=True),
        sa.Column("hsn", sa.String(length=20), nullable=True),
        sa.Column("purchase_price", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("treat_as_consume", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("raw_materials")
