"""pending_operations: staging table for unmapped operations (Operations Inbox)

Incremental migration on top of the baseline. Creates the single `pending_operations`
table that held the operations which didn't auto-resolve to a product.

NOTE: this table was later merged into `operations` (product_id NULL) by migration
merge_unmapped_ops_0003, and the model class no longer exists — so the DDL here is inline
raw SQL (CREATE IF NOT EXISTS) rather than imported from the model. On the live DB this
revision is already applied (won't re-run); on a fresh build it creates the table so 0003
can migrate + drop it.

Revision ID: pending_ops_0002
Revises: baseline_pf_0001
Create Date: 2026-06-15
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "pending_ops_0002"
down_revision: Union[str, Sequence[str], None] = "baseline_pf_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS pending_operations (
            id INTEGER NOT NULL PRIMARY KEY,
            raw_code VARCHAR(50) NOT NULL,
            raw_product_col VARCHAR(255),
            name VARCHAR(255),
            rate NUMERIC(15, 2),
            component VARCHAR(50),
            sequence INTEGER,
            side VARCHAR(5),
            guessed_stage_id INTEGER REFERENCES stages(id) ON DELETE SET NULL,
            suggested_part VARCHAR(100),
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            resolved_op_id INTEGER REFERENCES operations(id) ON DELETE SET NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            deleted_at DATETIME
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_pending_operations_raw_code ON pending_operations (raw_code)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_pending_operations_status ON pending_operations (status)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS pending_operations")
