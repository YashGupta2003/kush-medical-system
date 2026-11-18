"""Migration tests for the PharmOs Pulse heatmap schema (0026)."""
import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic" / "versions" / "0026_region_heatmap.py"
)


def _load_migration(operations):
    spec = importlib.util.spec_from_file_location("migration_0026", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = operations
    return module


def _engine_without_heatmap_tables():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    models.RegionHeatmapSnapshot.__table__.drop(engine, checkfirst=True)
    models.RegionHeatmapRun.__table__.drop(engine, checkfirst=True)
    return engine


def test_migration_creates_global_heatmap_tables_without_tenant_ids():
    engine = _engine_without_heatmap_tables()

    with engine.connect() as conn:
        operations = Operations(MigrationContext.configure(conn))
        migration = _load_migration(operations)
        migration.upgrade()
        conn.commit()

    inspector = inspect(engine)
    assert "region_heatmap_runs" in inspector.get_table_names()
    assert "region_heatmap_snapshots" in inspector.get_table_names()

    for table in ("region_heatmap_runs", "region_heatmap_snapshots"):
        columns = {column["name"] for column in inspector.get_columns(table)}
        assert "tenant_id" not in columns, "heatmap aggregates must stay global"


def test_migration_is_idempotent_and_reversible():
    engine = _engine_without_heatmap_tables()

    for _ in range(2):
        with engine.connect() as conn:
            operations = Operations(MigrationContext.configure(conn))
            _load_migration(operations).upgrade()
            conn.commit()

    with engine.connect() as conn:
        operations = Operations(MigrationContext.configure(conn))
        _load_migration(operations).downgrade()
        conn.commit()

    tables = inspect(engine).get_table_names()
    assert "region_heatmap_runs" not in tables
    assert "region_heatmap_snapshots" not in tables
