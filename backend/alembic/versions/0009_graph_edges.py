"""add graph_edges table (PharmaGraph - Pillar 1 knowledge graph)

Revision ID: 0009_graph_edges
Revises: 0008_medicine_composition
Create Date: 2026-08-02
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_graph_edges"
down_revision = "0008_medicine_composition"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "graph_edges",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("source_id", sa.String(150), nullable=False),
        sa.Column("edge_type", sa.String(30), nullable=False),
        sa.Column("target_type", sa.String(30), nullable=False),
        sa.Column("target_id", sa.String(150), nullable=False),
        sa.Column("weight", sa.Numeric(5, 2), nullable=True),
        sa.Column("edge_metadata", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_graph_edges_source", "graph_edges", ["source_type", "source_id"])
    op.create_index("ix_graph_edges_target", "graph_edges", ["target_type", "target_id"])
    op.create_index("ix_graph_edges_edge_type", "graph_edges", ["edge_type"])


def downgrade() -> None:
    op.drop_index("ix_graph_edges_edge_type", table_name="graph_edges")
    op.drop_index("ix_graph_edges_target", table_name="graph_edges")
    op.drop_index("ix_graph_edges_source", table_name="graph_edges")
    op.drop_table("graph_edges")
