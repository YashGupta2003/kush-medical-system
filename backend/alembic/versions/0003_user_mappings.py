"""add user_mappings table and 'learned' match_status

Revision ID: 0003_user_mappings
Revises: 0002_add_task_fields
Create Date: 2026-07-22
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_user_mappings"
down_revision = "0002_add_task_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_mappings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("distributor_id", sa.Integer(), sa.ForeignKey("distributors.id"), nullable=True),
        sa.Column("raw_name", sa.String(255), nullable=False),
        sa.Column("medicine_id", sa.Integer(), sa.ForeignKey("medicines.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_user_mappings_distributor_id", "user_mappings", ["distributor_id"])
    op.create_index("ix_user_mappings_raw_name", "user_mappings", ["raw_name"])
    op.alter_column(
        "bill_items", "match_status",
        existing_type=sa.Enum("auto", "manual", "unmatched", "confirmed", name="match_status"),
        type_=sa.Enum("auto", "learned", "manual", "unmatched", "confirmed", name="match_status"),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "bill_items", "match_status",
        existing_type=sa.Enum("auto", "learned", "manual", "unmatched", "confirmed", name="match_status"),
        type_=sa.Enum("auto", "manual", "unmatched", "confirmed", name="match_status"),
        existing_nullable=True,
    )
    op.drop_index("ix_user_mappings_raw_name", table_name="user_mappings")
    op.drop_index("ix_user_mappings_distributor_id", table_name="user_mappings")
    op.drop_table("user_mappings")
