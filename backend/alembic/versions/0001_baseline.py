"""baseline - marks existing schema as the migration starting point.
Run: alembic stamp 0001_baseline    (do NOT run "upgrade" for this one on an existing DB)

Revision ID: 0001_baseline
Revises:
Create Date: 2026-07-16
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
