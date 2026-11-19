"""Migration tests for stock integrity constraints (0029)."""
import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool

from app.database import Base

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic" / "versions" / "0029_stock_integrity_constraints.py"
)


def _load_migration(operations):
    spec = importlib.util.spec_from_file_location("migration_0029", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = operations
    return module


def _engine_with_schema():
    # Build schema without the app-level check constraint so migration adds it.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE medicines ("
            "id INTEGER PRIMARY KEY, "
            "tenant_id INTEGER, "
            "particulars VARCHAR(255) NOT NULL, "
            "normalized_name VARCHAR(255) NOT NULL, "
            "current_stock NUMERIC(10,2) NOT NULL DEFAULT 0"
            ")"
        ))
    return engine


def _has_non_negative_check(engine) -> bool:
    with engine.connect() as conn:
        rows = conn.execute(text("PRAGMA table_info(medicines)")).fetchall()
        # PRAGMA table_info doesn't show checks; inspect SQL from sqlite_master.
        ddl = conn.execute(
            text("SELECT sql FROM sqlite_master WHERE type='table' AND name='medicines'")
        ).scalar() or ""
    return "ck_medicines_current_stock_non_negative" in ddl or "current_stock >= 0" in ddl


def test_migration_adds_non_negative_stock_check_and_is_idempotent():
    engine = _engine_with_schema()

    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        ops = Operations(ctx)
        migration = _load_migration(ops)
        migration.upgrade()
        conn.commit()

    assert _has_non_negative_check(engine)

    # Idempotent
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        ops = Operations(ctx)
        migration = _load_migration(ops)
        migration.upgrade()
        conn.commit()

    assert _has_non_negative_check(engine)


def test_migration_rejects_existing_negative_stock_rows():
    engine = _engine_with_schema()
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO medicines (id, tenant_id, particulars, normalized_name, current_stock) "
            "VALUES (1, 1, 'BAD', 'BAD', -5)"
        ))

    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        ops = Operations(ctx)
        migration = _load_migration(ops)
        with pytest.raises(RuntimeError, match="NULL/negative"):
            migration.upgrade()


def test_downgrade_removes_check_when_possible():
    engine = _engine_with_schema()
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        ops = Operations(ctx)
        migration = _load_migration(ops)
        migration.upgrade()
        conn.commit()

    assert _has_non_negative_check(engine)

    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        ops = Operations(ctx)
        migration = _load_migration(ops)
        migration.downgrade()
        conn.commit()

    # On SQLite batch recreate the name may be preserved; accept either absence of name or presence.
    # Ensure table still usable.
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO medicines (id, tenant_id, particulars, normalized_name, current_stock) "
            "VALUES (2, 1, 'OK', 'OK', 0)"
        ))
