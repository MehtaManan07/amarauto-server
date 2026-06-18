"""merge pending_operations into operations as unmapped (product_id NULL)

The only thing that made an operation "pending" was a missing product. So instead of a
separate staging table, an unmapped operation is now just a row in `operations` with
product_id IS NULL. The raw CSV product text moves to operations.product_hint as a label
to help assign a product later (in-app).

This migration:
  1. operations.product_id -> NULLABLE, and adds operations.product_hint.
  2. Copies every pending_operations row into operations: product_id NULL,
     code <- raw_code, product_hint <- raw_product_col, stage_id <- guessed_stage_id,
     carrying name/rate/sequence/component/side/timestamps.
  3. Drops pending_operations.

Source data is also preserved in new-data/job-list.csv, so this is non-destructive.

Revision ID: merge_unmapped_ops_0003
Revises: pending_ops_0002
Create Date: 2026-06-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "merge_unmapped_ops_0003"
down_revision: Union[str, Sequence[str], None] = "pending_ops_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotent / fresh-build safe: the model-driven baseline may already produce the new
    # operations shape, and pending_operations may not exist. Guard each step.
    bind = op.get_bind()
    insp = sa.inspect(bind)
    op_cols = {c["name"] for c in insp.get_columns("operations")}
    tables = set(insp.get_table_names())

    # 1. product_id nullable + new product_hint column (one table rebuild) — only if needed.
    if "product_hint" not in op_cols:
        with op.batch_alter_table("operations", recreate="always") as batch_op:
            batch_op.add_column(sa.Column("product_hint", sa.String(length=255), nullable=True))
            batch_op.alter_column("product_id", existing_type=sa.Integer(), nullable=True)

    # 2 & 3. Move the unmapped ops in, then drop the staging table — only if it exists.
    if "pending_operations" in tables:
        # name is NOT NULL on operations, so COALESCE.
        op.execute(
            """
            INSERT INTO operations
                (product_id, stage_id, code, name, rate, sequence, component, side,
                 product_hint, created_at, updated_at, deleted_at)
            SELECT
                NULL, guessed_stage_id, raw_code, COALESCE(name, raw_code), rate, sequence,
                component, side, raw_product_col, created_at, updated_at, deleted_at
            FROM pending_operations
            """
        )
        op.execute("DROP TABLE pending_operations")


def downgrade() -> None:
    # Recreate the staging table (DDL hardcoded — the model no longer defines it).
    op.execute(
        """
        CREATE TABLE pending_operations (
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
    op.execute("CREATE INDEX ix_pending_operations_raw_code ON pending_operations (raw_code)")
    op.execute("CREATE INDEX ix_pending_operations_status ON pending_operations (status)")

    # Move unmapped ops (product_id IS NULL) back out.
    op.execute(
        """
        INSERT INTO pending_operations
            (raw_code, raw_product_col, name, rate, component, sequence, side,
             guessed_stage_id, status, created_at, updated_at, deleted_at)
        SELECT
            code, product_hint, name, rate, component, sequence, side,
            stage_id, 'pending', created_at, updated_at, deleted_at
        FROM operations
        WHERE product_id IS NULL
        """
    )
    op.execute("DELETE FROM operations WHERE product_id IS NULL")

    # product_id back to NOT NULL + drop product_hint.
    with op.batch_alter_table("operations", recreate="always") as batch_op:
        batch_op.alter_column("product_id", existing_type=sa.Integer(), nullable=False)
        batch_op.drop_column("product_hint")
