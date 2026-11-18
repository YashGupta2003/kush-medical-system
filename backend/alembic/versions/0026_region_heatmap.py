"""PharmOs Pulse — privacy-preserving regional heatmap snapshots.

Revision ID: 0026
Revises: 0025

Stores k-anonymous (k >= 3) aggregated health signals by region and
condition. These tables are intentionally GLOBAL: they are aggregates over
multiple opted-in tenants and must never carry a tenant_id. Privacy is
enforced by the aggregation service and by a sanitized API DTO, not by
tenant scoping the aggregate table.
"""
from alembic import op
import sqlalchemy as sa

revision = '0026'
down_revision = '0025'
branch_labels = None
depends_on = None


def _tables():
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade():
    existing = _tables()

    if "region_heatmap_runs" not in existing:
        op.create_table(
            "region_heatmap_runs",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("window_start", sa.Date(), nullable=False),
            sa.Column("window_end", sa.Date(), nullable=False),
            sa.Column("window_days", sa.Integer(), nullable=False),
            sa.Column("published_cells", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("suppressed_cells", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("regions_scanned", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("payload_hash", sa.String(64), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.UniqueConstraint("window_start", "window_end", name="uix_heatmap_run_window"),
        )
        op.create_index("ix_region_heatmap_runs_window_end", "region_heatmap_runs", ["window_end"])

    if "region_heatmap_snapshots" not in existing:
        op.create_table(
            "region_heatmap_snapshots",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column(
                "run_id",
                sa.Integer(),
                sa.ForeignKey("region_heatmap_runs.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("region_code", sa.String(50), nullable=False, index=True),
            sa.Column("condition_name", sa.String(150), nullable=False, index=True),
            sa.Column("signal_level", sa.String(20), nullable=False),
            sa.Column("trend", sa.String(10), nullable=False),
            sa.Column("trend_labels_json", sa.Text(), nullable=True),
            sa.Column("contributor_count", sa.Integer(), nullable=False),
            sa.Column("public_volume_band", sa.String(20), nullable=False),
            # Internal explainability only; the public API never exposes it.
            sa.Column("total_units", sa.Integer(), nullable=False),
            sa.Column("z_score", sa.Numeric(6, 3), nullable=False),
            sa.Column("confidence", sa.String(10), nullable=False),
            sa.Column("payload_hash", sa.String(64), nullable=False),
            sa.Column("computed_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint(
                "run_id", "region_code", "condition_name",
                name="uix_heatmap_cell_run_region_condition",
            ),
        )
        # run_id / region_code / condition_name indexes are created by the
        # index=True flags on the columns above.


def downgrade():
    existing = _tables()
    if "region_heatmap_snapshots" in existing:
        op.drop_table("region_heatmap_snapshots")
    if "region_heatmap_runs" in existing:
        op.drop_table("region_heatmap_runs")
