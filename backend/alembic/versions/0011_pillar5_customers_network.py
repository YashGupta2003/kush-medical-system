"""add customers, credit ledger, sales.customer_id, and inter-pharmacy network tables (Pillar 5)

Revision ID: 0011_pillar5_customers_network
Revises: 0010_audit_ledger
Create Date: 2026-08-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_pillar5_customers_network"
down_revision = "0010_audit_ledger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("phone", sa.String(15), nullable=False),
        sa.Column("name", sa.String(100), nullable=True),
        sa.Column("consent_given_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_customers_phone", "customers", ["phone"], unique=True)

    op.add_column("sales", sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=True))
    op.create_index("ix_sales_customer_id", "sales", ["customer_id"])

    op.create_table(
        "customer_credit_ledger",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("change_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("resulting_balance", sa.Numeric(10, 2), nullable=False),
        sa.Column("reason", sa.Enum("credit_sale", "payment_received", "adjustment", name="credit_reason"), nullable=False),
        sa.Column("reference_sale_id", sa.Integer(), sa.ForeignKey("sales.id"), nullable=True),
        sa.Column("note", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_customer_credit_ledger_customer_id", "customer_credit_ledger", ["customer_id"])

    op.create_table(
        "pharmacy_nodes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("shop_name", sa.String(150), nullable=False),
        sa.Column("api_base_url", sa.String(255), nullable=True),
        sa.Column("contact_phone", sa.String(50), nullable=True),
        sa.Column("is_self", sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.Column("opted_in", sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column("joined_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "network_listings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("pharmacy_node_id", sa.Integer(), sa.ForeignKey("pharmacy_nodes.id"), nullable=False),
        sa.Column("listing_type", sa.Enum("near_expiry", "excess_stock", "shortage_request", name="listing_type"), nullable=False),
        sa.Column("medicine_name", sa.String(255), nullable=False),
        sa.Column("composition", sa.String(500), nullable=True),
        sa.Column("quantity", sa.Numeric(10, 2), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("note", sa.String(255), nullable=True),
        sa.Column("status", sa.Enum("open", "claimed", "fulfilled", "withdrawn", name="listing_status"), nullable=False, server_default="open"),
        sa.Column("claimed_by_node_id", sa.Integer(), sa.ForeignKey("pharmacy_nodes.id"), nullable=True),
        sa.Column("source_batch_id", sa.Integer(), sa.ForeignKey("medicine_batches.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_network_listings_status", "network_listings", ["status"])
    op.create_index("ix_network_listings_listing_type", "network_listings", ["listing_type"])


def downgrade() -> None:
    op.drop_index("ix_network_listings_listing_type", table_name="network_listings")
    op.drop_index("ix_network_listings_status", table_name="network_listings")
    op.drop_table("network_listings")
    op.drop_table("pharmacy_nodes")
    op.drop_index("ix_customer_credit_ledger_customer_id", table_name="customer_credit_ledger")
    op.drop_table("customer_credit_ledger")
    op.drop_index("ix_sales_customer_id", table_name="sales")
    op.drop_column("sales", "customer_id")
    op.drop_index("ix_customers_phone", table_name="customers")
    op.drop_table("customers")