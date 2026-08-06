"""add audit_ledger table (TrustChain - Pillar 4 tamper-evident audit trail)

Revision ID: 0010_audit_ledger
Revises: 0009_graph_edges
Create Date: 2026-08-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_audit_ledger"
down_revision = "0009_graph_edges"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_ledger",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("reference_id", sa.Integer(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("entry_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_audit_ledger_event_type", "audit_ledger", ["event_type"])
    op.create_index("ix_audit_ledger_reference_id", "audit_ledger", ["reference_id"])
    op.create_index("ix_audit_ledger_entry_hash", "audit_ledger", ["entry_hash"])
    op.create_index("ix_audit_ledger_created_at", "audit_ledger", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_ledger_created_at", table_name="audit_ledger")
    op.drop_index("ix_audit_ledger_entry_hash", table_name="audit_ledger")
    op.drop_index("ix_audit_ledger_reference_id", table_name="audit_ledger")
    op.drop_index("ix_audit_ledger_event_type", table_name="audit_ledger")
    op.drop_table("audit_ledger")