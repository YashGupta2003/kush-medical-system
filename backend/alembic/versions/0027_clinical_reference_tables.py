"""Store shared clinical reference data in database tables.

Revision ID: 0027
Revises: 0026

The tables are global: the curated baseline is shared by all pharmacy tenants.
"""
from alembic import op
import sqlalchemy as sa


revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def upgrade():
    inspector = _inspector()
    tables = set(inspector.get_table_names())

    if "salt_conditions" not in tables:
        op.create_table(
            "salt_conditions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("salt_name", sa.String(length=255), nullable=False),
            sa.Column("conditions", sa.JSON(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("salt_name", name="uq_salt_conditions_salt_name"),
        )

    inspector = _inspector()
    salt_indexes = {index["name"] for index in inspector.get_indexes("salt_conditions")}
    if "ix_salt_conditions_salt_name" not in salt_indexes:
        op.create_index("ix_salt_conditions_salt_name", "salt_conditions", ["salt_name"])

    inspector = _inspector()
    tables = set(inspector.get_table_names())
    if "drug_interactions" not in tables:
        op.create_table(
            "drug_interactions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("salt_a", sa.String(length=255), nullable=False),
            sa.Column("salt_b", sa.String(length=255), nullable=False),
            sa.Column("severity", sa.String(length=30), nullable=False),
            sa.Column("note", sa.Text(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("salt_a", "salt_b", name="uq_drug_interactions_salt_pair"),
        )

    inspector = _inspector()
    interaction_indexes = {index["name"] for index in inspector.get_indexes("drug_interactions")}
    if "ix_drug_interactions_salt_a" not in interaction_indexes:
        op.create_index("ix_drug_interactions_salt_a", "drug_interactions", ["salt_a"])
    if "ix_drug_interactions_salt_b" not in interaction_indexes:
        op.create_index("ix_drug_interactions_salt_b", "drug_interactions", ["salt_b"])


def downgrade():
    tables = set(_inspector().get_table_names())
    if "drug_interactions" in tables:
        op.drop_table("drug_interactions")
    if "salt_conditions" in tables:
        op.drop_table("salt_conditions")
