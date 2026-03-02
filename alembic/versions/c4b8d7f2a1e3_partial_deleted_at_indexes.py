"""Replace full deleted_at indexes with partial (WHERE deleted_at IS NULL) indexes

Revision ID: c4b8d7f2a1e3
Revises: b3a1f7c9d2e4
Create Date: 2026-03-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c4b8d7f2a1e3'
down_revision: Union[str, Sequence[str], None] = 'b3a1f7c9d2e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tables that had full deleted_at indexes and need partial replacements
_TABLES = [
    'products',
    'raw_materials',
    'parties',
    'bom_lines',
    'stage_inventory',
    'work_logs',
    'users',
    'job_rates',
    'inventory_logs',
]


def upgrade() -> None:
    """Drop full deleted_at indexes; create partial WHERE deleted_at IS NULL indexes.

    A partial index only covers active (non-deleted) rows, which are the vast
    majority. Every list/find query filters by deleted_at IS NULL, so the planner
    can use these much-smaller indexes instead of scanning the full table.
    """
    for table in _TABLES:
        op.execute(f"DROP INDEX IF EXISTS ix_{table}_deleted_at")
        op.execute(
            f"CREATE INDEX IF NOT EXISTS ix_{table}_active "
            f"ON {table}(id) WHERE deleted_at IS NULL"
        )


def downgrade() -> None:
    """Drop partial indexes; restore full deleted_at indexes."""
    for table in _TABLES:
        op.execute(f"DROP INDEX IF EXISTS ix_{table}_active")
        op.execute(
            f"CREATE INDEX IF NOT EXISTS ix_{table}_deleted_at "
            f"ON {table}(deleted_at)"
        )
