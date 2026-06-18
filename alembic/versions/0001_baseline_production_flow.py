"""baseline: production-flow schema (squashed)

Single fresh baseline that replaces the 16 pre-restructure migrations. Creates the full
production-flow schema and seeds the 4 stages.

Why create_all instead of explicit op.create_table:
  - The target Turso DB (`amarauto`) already contains `users` + `parties` (imported by hand,
    no alembic_version stamp). `metadata.create_all(checkfirst=True)` creates every *missing*
    table and SKIPS the two that already exist — which is exactly the cutover we want, and
    resolves the old "CREATE TABLE users already exists" conflict.
  - On a brand-new/empty DB it simply builds all 14 tables.

All models are imported by alembic/env.py before this runs, so Base.metadata is complete.

Revision ID: baseline_pf_0001
Revises:
Create Date: 2026-06-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.core.db.base import Base

# revision identifiers, used by Alembic.
revision: str = "baseline_pf_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Stage seed data: name -> global sequence. A product's real path is derived from its
# recipe (many products skip stitching); these are just the ordered stage definitions.
STAGES = [
    {"name": "CUTTING", "sequence": 1},
    {"name": "STITCHING", "sequence": 2},
    {"name": "FINISHING", "sequence": 3},
    {"name": "ASSEMBLY", "sequence": 4},
]


def upgrade() -> None:
    bind = op.get_bind()
    # Create every missing table (skips pre-existing users/parties on the live DB).
    Base.metadata.create_all(bind, checkfirst=True)

    # Seed stages (created_at/updated_at/is_active fall back to their server defaults).
    stages_tbl = sa.table(
        "stages",
        sa.column("name", sa.String),
        sa.column("sequence", sa.Integer),
    )
    op.bulk_insert(stages_tbl, STAGES)


def downgrade() -> None:
    # Full teardown of the baseline schema.
    Base.metadata.drop_all(op.get_bind())
