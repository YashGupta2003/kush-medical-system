"""add medicine_batches table for expiry tracking

Revision ID: 0005_expiry_tracking
Revises: 0004_stock_tracking
Create Date: 2026-07-23
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_expiry_tracking"
down_revision = "0004_stock_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "medicine_batches",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("medicine_id", sa.Integer(), sa.ForeignKey("medicines.id"), nullable=False),
        sa.Column("batch_no", sa.String(50), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("qty_received", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("bill_item_id", sa.Integer(), sa.ForeignKey("bill_items.id"), nullable=True, unique=True),
        sa.Column("distributor_id", sa.Integer(), sa.ForeignKey("distributors.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_medicine_batches_medicine_id", "medicine_batches", ["medicine_id"])
    op.create_index("ix_medicine_batches_expiry_date", "medicine_batches", ["expiry_date"])


def downgrade() -> None:
    op.drop_index("ix_medicine_batches_expiry_date", table_name="medicine_batches")
    op.drop_index("ix_medicine_batches_medicine_id", table_name="medicine_batches")
    op.drop_table("medicine_batches")
