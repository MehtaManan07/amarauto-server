"""parties

Revision ID: a1b2c3d4e5f6
Revises: 210134fb50a7
Create Date: 2026-02-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '210134fb50a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'parties',
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('state', sa.String(length=100), nullable=True),
        sa.Column('party_type', sa.String(length=100), nullable=True),
        sa.Column('address_line_1', sa.String(length=500), nullable=True),
        sa.Column('address_line_2', sa.String(length=500), nullable=True),
        sa.Column('address_line_3', sa.String(length=500), nullable=True),
        sa.Column('address_line_4', sa.String(length=500), nullable=True),
        sa.Column('address_line_5', sa.String(length=500), nullable=True),
        sa.Column('pin_code', sa.String(length=20), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('fax', sa.String(length=50), nullable=True),
        sa.Column('contact_person', sa.String(length=255), nullable=True),
        sa.Column('mobile', sa.String(length=50), nullable=True),
        sa.Column('gstin', sa.String(length=50), nullable=True),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('parties', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_parties_name'), ['name'], unique=True)
        batch_op.create_index(batch_op.f('ix_parties_state'), ['state'], unique=False)
        batch_op.create_index(batch_op.f('ix_parties_party_type'), ['party_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_parties_gstin'), ['gstin'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('parties', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_parties_name'))
        batch_op.drop_index(batch_op.f('ix_parties_state'))
        batch_op.drop_index(batch_op.f('ix_parties_party_type'))
        batch_op.drop_index(batch_op.f('ix_parties_gstin'))
    op.drop_table('parties')
