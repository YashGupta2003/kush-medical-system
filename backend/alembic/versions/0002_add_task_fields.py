"""add task queue, OCR confidence, and needs_attention fields to bills

Revision ID: 0002_add_task_fields
Revises: 0001_baseline
Create Date: 2026-07-16
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_add_task_fields"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bills", sa.Column("celery_task_id", sa.String(100), nullable=True))
    op.add_column("bills", sa.Column("processing_error", sa.Text(), nullable=True))
    op.add_column("bills", sa.Column("ocr_confidence", sa.Numeric(5, 2), nullable=True))
    op.add_column("bills", sa.Column("needs_attention_reason", sa.String(255), nullable=True))
    op.add_column("bills", sa.Column("preprocessing_notes", sa.Text(), nullable=True))
    op.create_index("ix_bills_celery_task_id", "bills", ["celery_task_id"])
    op.alter_column(
        "bills", "status",
        existing_type=sa.Enum("pending_review", "confirmed", "rejected", name="bill_status"),
        type_=sa.Enum("queued", "processing", "pending_review", "needs_attention",
                       "confirmed", "rejected", "failed", name="bill_status"),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.drop_index("ix_bills_celery_task_id", table_name="bills")
    op.drop_column("bills", "preprocessing_notes")
    op.drop_column("bills", "needs_attention_reason")
    op.drop_column("bills", "ocr_confidence")
    op.drop_column("bills", "processing_error")
    op.drop_column("bills", "celery_task_id")
    op.alter_column(
        "bills", "status",
        existing_type=sa.Enum("queued", "processing", "pending_review", "needs_attention",
                               "confirmed", "rejected", "failed", name="bill_status"),
        type_=sa.Enum("pending_review", "confirmed", "rejected", name="bill_status"),
        existing_nullable=True,
    )
