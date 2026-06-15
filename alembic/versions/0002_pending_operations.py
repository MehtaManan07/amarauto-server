"""pending_operations: staging table for unmapped operations (Operations Inbox)

Incremental migration on top of the baseline. Creates the single `pending_operations`
table that holds the 124 operations which didn't auto-resolve to a product, so they can be
worked off as an in-app inbox instead of living in the source CSV.

Created from the model's own table definition (checkfirst=True) so the DDL can never drift
from the model.

Revision ID: pending_ops_0002
Revises: baseline_pf_0001
Create Date: 2026-06-15
"""
from typing import Sequence, Union

from alembic import op

from app.modules.operations.models import PendingOperation

# revision identifiers, used by Alembic.
revision: str = "pending_ops_0002"
down_revision: Union[str, Sequence[str], None] = "baseline_pf_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    PendingOperation.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    PendingOperation.__table__.drop(op.get_bind(), checkfirst=True)
