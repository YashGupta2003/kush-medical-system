"""add medicine composition + medicine_salts table (Substitute Medicine Suggestion feature)

Revision ID: 0008_medicine_composition
Revises: 0007_smart_reorder
Create Date: 2026-07-31
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_medicine_composition"
down_revision = "0007_smart_reorder"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("medicines", sa.Column("composition", sa.String(500), nullable=True))

    op.create_table(
        "medicine_salts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("medicine_id", sa.Integer(), sa.ForeignKey("medicines.id"), nullable=False),
        sa.Column("salt_name", sa.String(150), nullable=False),
        sa.Column("strength", sa.String(50), nullable=True),
    )
    op.create_index("ix_medicine_salts_medicine_id", "medicine_salts", ["medicine_id"])
    op.create_index("ix_medicine_salts_salt_name", "medicine_salts", ["salt_name"])


def downgrade() -> None:
    op.drop_index("ix_medicine_salts_salt_name", table_name="medicine_salts")
    op.drop_index("ix_medicine_salts_medicine_id", table_name="medicine_salts")
    op.drop_table("medicine_salts")
    op.drop_column("medicines", "composition")
