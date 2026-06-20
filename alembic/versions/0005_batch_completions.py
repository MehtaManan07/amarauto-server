"""add batch_completions table

Revision ID: 0005_batch_completions
Revises: 0004_batch_completed_at
Create Date: 2026-06-21
"""
from alembic import op
import sqlalchemy as sa

revision = '0005_batch_completions'
down_revision = '0004_batch_completed_at'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'batch_completions',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('batch_id', sa.Integer, sa.ForeignKey('batches.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('stage_id', sa.Integer, sa.ForeignKey('stages.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('quantity', sa.Numeric(15, 2), nullable=False),
        sa.Column('completed_by', sa.Integer, sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=False), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=False), server_default=sa.func.now(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=False), nullable=True),
    )

def downgrade():
    op.drop_table('batch_completions')
