"""add stock_ledger.created_by_user_id (Pillar 6 - lets anomaly/pilferage
detection attribute manual stock adjustments to a staff account)

Revision ID: 0012_pillar6_predictive
Revises: 0011_pillar5_customers_network
Create Date: 2026-08-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0012_pillar6_predictive"
down_revision = "0011_pillar5_customers_network"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stock_ledger",
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_stock_ledger_created_by_user_id", "stock_ledger", ["created_by_user_id"])


def downgrade() -> None:
    op.drop_index("ix_stock_ledger_created_by_user_id", table_name="stock_ledger")
    op.drop_column("stock_ledger", "created_by_user_id")