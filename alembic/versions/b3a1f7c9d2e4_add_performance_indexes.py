"""add performance indexes

Revision ID: b3a1f7c9d2e4
Revises: fba5baeac847
Create Date: 2026-03-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b3a1f7c9d2e4'
down_revision: Union[str, Sequence[str], None] = 'fba5baeac847'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add indexes for hot query paths — deleted_at, stage lookups, composite keys."""

    # deleted_at on every table (every list query filters by deleted_at IS NULL)
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.create_index('ix_products_deleted_at', ['deleted_at'])

    with op.batch_alter_table('raw_materials', schema=None) as batch_op:
        batch_op.create_index('ix_raw_materials_deleted_at', ['deleted_at'])

    with op.batch_alter_table('parties', schema=None) as batch_op:
        batch_op.create_index('ix_parties_deleted_at', ['deleted_at'])

    with op.batch_alter_table('bom_lines', schema=None) as batch_op:
        batch_op.create_index('ix_bom_lines_deleted_at', ['deleted_at'])
        # stage_number single + composite with product_id
        batch_op.create_index('ix_bom_lines_stage_number', ['stage_number'])
        batch_op.create_index('ix_bom_product_stage', ['product_id', 'stage_number'])

    with op.batch_alter_table('stage_inventory', schema=None) as batch_op:
        batch_op.create_index('ix_stage_inventory_deleted_at', ['deleted_at'])
        # composite index for the (product_id, stage_number, variant) WHERE clause
        batch_op.create_index('ix_stage_inv_lookup', ['product_id', 'stage_number', 'variant'])

    with op.batch_alter_table('work_logs', schema=None) as batch_op:
        batch_op.create_index('ix_work_logs_deleted_at', ['deleted_at'])

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index('ix_users_deleted_at', ['deleted_at'])

    with op.batch_alter_table('job_rates', schema=None) as batch_op:
        batch_op.create_index('ix_job_rates_deleted_at', ['deleted_at'])

    with op.batch_alter_table('inventory_logs', schema=None) as batch_op:
        batch_op.create_index('ix_inventory_logs_deleted_at', ['deleted_at'])


def downgrade() -> None:
    """Remove performance indexes."""

    with op.batch_alter_table('inventory_logs', schema=None) as batch_op:
        batch_op.drop_index('ix_inventory_logs_deleted_at')

    with op.batch_alter_table('job_rates', schema=None) as batch_op:
        batch_op.drop_index('ix_job_rates_deleted_at')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index('ix_users_deleted_at')

    with op.batch_alter_table('work_logs', schema=None) as batch_op:
        batch_op.drop_index('ix_work_logs_deleted_at')

    with op.batch_alter_table('stage_inventory', schema=None) as batch_op:
        batch_op.drop_index('ix_stage_inv_lookup')
        batch_op.drop_index('ix_stage_inventory_deleted_at')

    with op.batch_alter_table('bom_lines', schema=None) as batch_op:
        batch_op.drop_index('ix_bom_product_stage')
        batch_op.drop_index('ix_bom_lines_stage_number')
        batch_op.drop_index('ix_bom_lines_deleted_at')

    with op.batch_alter_table('parties', schema=None) as batch_op:
        batch_op.drop_index('ix_parties_deleted_at')

    with op.batch_alter_table('raw_materials', schema=None) as batch_op:
        batch_op.drop_index('ix_raw_materials_deleted_at')

    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.drop_index('ix_products_deleted_at')
