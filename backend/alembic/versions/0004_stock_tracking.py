"""add stock tracking tables and Medicine stock columns

Revision ID: 0004_stock_tracking
Revises: 0003_user_mappings
Create Date: 2026-07-23
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_stock_tracking"
down_revision = "0003_user_mappings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("medicines", sa.Column("current_stock", sa.Numeric(10, 2), nullable=False, server_default="0"))
    op.add_column("medicines", sa.Column("low_stock_threshold", sa.Numeric(10, 2), nullable=True))

    op.create_table(
        "sales",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("medicine_id", sa.Integer(), sa.ForeignKey("medicines.id"), nullable=False),
        sa.Column("qty_sold", sa.Numeric(10, 2), nullable=False),
        sa.Column("sold_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_sales_medicine_id", "sales", ["medicine_id"])

    op.create_table(
        "stock_ledger",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("medicine_id", sa.Integer(), sa.ForeignKey("medicines.id"), nullable=False),
        sa.Column("change_qty", sa.Numeric(10, 2), nullable=False),
        sa.Column("resulting_balance", sa.Numeric(10, 2), nullable=False),
        sa.Column("reason", sa.Enum("bill_received", "sale", "manual_adjustment", name="stock_reason"), nullable=False),
        sa.Column("reference_bill_item_id", sa.Integer(), sa.ForeignKey("bill_items.id"), nullable=True),
        sa.Column("reference_sale_id", sa.Integer(), sa.ForeignKey("sales.id"), nullable=True),
        sa.Column("note", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_stock_ledger_medicine_id", "stock_ledger", ["medicine_id"])

    op.create_table(
        "reorder_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("medicine_id", sa.Integer(), sa.ForeignKey("medicines.id"), nullable=True),
        sa.Column("custom_name", sa.String(255), nullable=True),
        sa.Column("distributor_id", sa.Integer(), sa.ForeignKey("distributors.id"), nullable=True),
        sa.Column("quantity_needed", sa.Numeric(10, 2), nullable=True),
        sa.Column("note", sa.String(255), nullable=True),
        sa.Column("source", sa.Enum("auto_low_stock", "manual", name="reorder_source"), nullable=True),
        sa.Column("fulfilled", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("reorder_items")
    op.drop_index("ix_stock_ledger_medicine_id", table_name="stock_ledger")
    op.drop_table("stock_ledger")
    op.drop_index("ix_sales_medicine_id", table_name="sales")
    op.drop_table("sales")
    op.drop_column("medicines", "low_stock_threshold")
    op.drop_column("medicines", "current_stock")
