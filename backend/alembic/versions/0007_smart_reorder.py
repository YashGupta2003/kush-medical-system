"""add smart reorder point engine columns to medicines table

Revision ID: 0007_smart_reorder
Revises: 0006_auth_and_barcode
Create Date: 2026-07-30
"""
from alembic import op
import sqlalchemy as sa


revision = "0007_smart_reorder"
down_revision = "0006_auth_and_barcode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("medicines", sa.Column("lead_time_days", sa.Integer(), nullable=True))
    op.add_column("medicines", sa.Column("suggested_low_stock_threshold", sa.Numeric(10, 2), nullable=True))
    op.add_column("medicines", sa.Column("avg_daily_sales_30d", sa.Numeric(10, 2), nullable=True))
    op.add_column("medicines", sa.Column("suggestion_computed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("medicines", "suggestion_computed_at")
    op.drop_column("medicines", "avg_daily_sales_30d")
    op.drop_column("medicines", "suggested_low_stock_threshold")
    op.drop_column("medicines", "lead_time_days")
