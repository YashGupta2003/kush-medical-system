"""Tenant schema hardening

Revision ID: 0021
Revises: 0020
Create Date: 2026-09-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

revision = '0021'
down_revision = '0020'
branch_labels = None
depends_on = None

def upgrade():
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    if "bills" in tables:
        columns = [c["name"] for c in inspector.get_columns("bills")]
        if "checksum" not in columns:
            op.add_column("bills", sa.Column("checksum", sa.String(64), nullable=True))
            op.create_index("ix_bills_checksum", "bills", ["checksum"])

    if "tenants" in tables:
        tenant_columns = [c["name"] for c in inspector.get_columns("tenants")]
        if "slug" not in tenant_columns:
            op.add_column("tenants", sa.Column("slug", sa.String(80), nullable=True))
        if "shop_name" not in tenant_columns:
            op.add_column("tenants", sa.Column("shop_name", sa.String(150), nullable=True))
        if "owner_name" not in tenant_columns:
            op.add_column("tenants", sa.Column("owner_name", sa.String(150), nullable=True))
        if "gstin" not in tenant_columns:
            op.add_column("tenants", sa.Column("gstin", sa.String(20), nullable=True))
        if "city" not in tenant_columns:
            op.add_column("tenants", sa.Column("city", sa.String(100), nullable=True))
        if "address" not in tenant_columns:
            op.add_column("tenants", sa.Column("address", sa.Text(), nullable=True))
        if "plan" not in tenant_columns:
            op.add_column("tenants", sa.Column("plan", sa.String(50), server_default="free"))
        if "is_active" not in tenant_columns:
            op.add_column("tenants", sa.Column("is_active", sa.Boolean(), server_default="1"))
        if "email_verified" not in tenant_columns:
            op.add_column("tenants", sa.Column("email_verified", sa.Boolean(), server_default="0"))
        if "email_verification_token" not in tenant_columns:
            op.add_column("tenants", sa.Column("email_verification_token", sa.String(64), nullable=True))

    if "refresh_tokens" in tables:
        rt_columns = [c["name"] for c in inspector.get_columns("refresh_tokens")]
        if "tenant_id" not in rt_columns:
            op.add_column("refresh_tokens", sa.Column("tenant_id", sa.Integer(), nullable=True))
            try:
                op.create_foreign_key("fk_refresh_tokens_tenant", "refresh_tokens", "tenants", ["tenant_id"], ["id"])
                op.create_index("ix_refresh_tokens_tenant_id", "refresh_tokens", ["tenant_id"])
            except Exception:
                pass

    for table in tables:
        if table in ("tenants", "alembic_version"):
            continue
        columns = [c["name"] for c in inspector.get_columns(table)]
        if "tenant_id" not in columns:
            op.add_column(table, sa.Column("tenant_id", sa.Integer(), nullable=True))
            try:
                op.create_foreign_key(f"fk_{table}_tenant", table, "tenants", ["tenant_id"], ["id"])
                op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"])
            except Exception:
                pass

def downgrade():
    pass
