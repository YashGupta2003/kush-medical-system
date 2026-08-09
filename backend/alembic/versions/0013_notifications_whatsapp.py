"""0013_notifications_whatsapp

Adds:
  - notifications table (Pillar 7 Notification Engine)
  - refresh_tokens table (Priority 2a: refresh token flow)
  - users.whatsapp_number nullable column (WhatsApp delivery)

Revision ID: 0013
Revises: 0012_pillar6_predictive
"""
from alembic import op
import sqlalchemy as sa

revision = "0013_notifications_whatsapp"
down_revision = "0012_pillar6_predictive"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- users.whatsapp_number ---
    op.add_column(
        "users",
        sa.Column("whatsapp_number", sa.String(20), nullable=True),
    )

    # --- refresh_tokens ---
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked", sa.Boolean(), default=False, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )

    # --- notifications ---
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("recipient_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True, index=True),
        sa.Column(
            "notification_type",
            sa.Enum(
                "adherence_overdue",
                "anomaly_flagged",
                "low_stock_crossed",
                "credit_overdue",
                "trust_chain_tamper",
                "near_expiry",
                "daily_digest",
                "system",
                name="notification_type",
            ),
            nullable=False,
            index=True,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "severity",
            sa.Enum("info", "warning", "critical", name="notification_severity"),
            nullable=False,
            server_default="info",
        ),
        sa.Column("related_entity_type", sa.String(50), nullable=True),
        sa.Column("related_entity_id", sa.String(50), nullable=True),
        sa.Column(
            "channel",
            sa.Enum("in_app", "whatsapp", "sms", "email", name="notification_channel"),
            nullable=False,
            server_default="in_app",
        ),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("refresh_tokens")
    op.drop_column("users", "whatsapp_number")

    # Drop enums created in upgrade (MySQL drops them with the table, but guard for other DBs)
    try:
        sa.Enum(name="notification_type").drop(op.get_bind(), checkfirst=True)
        sa.Enum(name="notification_severity").drop(op.get_bind(), checkfirst=True)
        sa.Enum(name="notification_channel").drop(op.get_bind(), checkfirst=True)
    except Exception:
        pass
