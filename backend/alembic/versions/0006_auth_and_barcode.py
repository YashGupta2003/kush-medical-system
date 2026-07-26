"""add users table (auth) and barcode column on medicines

Revision ID: 0006_auth_and_barcode
Revises: 0005_expiry_tracking
Create Date: 2026-07-24
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_auth_and_barcode"
down_revision = "0005_expiry_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("medicines", sa.Column("barcode", sa.String(64), nullable=True))
    op.create_index("ix_medicines_barcode", "medicines", ["barcode"], unique=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(100), nullable=True),
        sa.Column("role", sa.Enum("owner", "staff", name="user_role"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_medicines_barcode", table_name="medicines")
    op.drop_column("medicines", "barcode")
