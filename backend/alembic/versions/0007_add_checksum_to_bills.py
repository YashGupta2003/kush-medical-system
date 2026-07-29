"""add checksum to bills

Revision ID: 0007_add_checksum_to_bills
Revises: 0006_auth_and_barcode
Create Date: 2026-07-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_add_checksum_to_bills"
down_revision = "0006_auth_and_barcode"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("bills", sa.Column("checksum", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_bills_checksum"), "bills", ["checksum"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_bills_checksum"), table_name="bills")
    op.drop_column("bills", "checksum")
