"""add completed_at to batches

Revision ID: 0004_batch_completed_at
Revises: 0003_merge_unmapped_ops
Create Date: 2026-06-21
"""
from alembic import op
import sqlalchemy as sa

revision = '0004_batch_completed_at'
down_revision = "merge_unmapped_ops_0003"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('batches', sa.Column('completed_at', sa.DateTime(timezone=False), nullable=True))

def downgrade():
    op.drop_column('batches', 'completed_at')
