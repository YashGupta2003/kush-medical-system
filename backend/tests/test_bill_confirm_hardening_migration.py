"""Migration tests for bill confirmation hardening (0030)."""
import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic" / "versions" / "0030_bill_confirm_hardening.py"
)


def _load_migration(operations):
    spec = importlib.util.spec_from_file_location("migration_0030", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = operations
    return module


def _engine_with_legacy_bills():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE bills ("
            "id INTEGER PRIMARY KEY, "
            "tenant_id INTEGER, "
            "distributor_id INTEGER, "
            "invoice_no VARCHAR(100), "
            "status VARCHAR(30)"
            ")"
        ))
    return engine


def _ddl(engine):
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT sql FROM sqlite_master WHERE type='table' AND name='bills'")
        ).scalar() or ""


def test_migration_adds_column_backfills_confirmed_and_enforces_uniqueness():
    engine = _engine_with_legacy_bills()
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO bills (id, tenant_id, distributor_id, invoice_no, status) "
            "VALUES (1, 1, 10, ' inv-001 ', 'confirmed'),"
            "       (2, 1, 10, 'INV-002', 'confirmed'),"
            "       (3, 1, 10, 'INV-001', 'pending_review')"
        ))

    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        ops = Operations(ctx)
        migration = _load_migration(ops)
        migration.upgrade()
        conn.commit()

    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, confirmed_invoice_key FROM bills ORDER BY id"
        )).fetchall()
    assert rows == [
        (1, "1:10:INV-001"),
        (2, "1:10:INV-002"),
        (3, None),
    ]

    # Unique guard should reject duplicate confirmed key on insert/update.
    with pytest.raises(sa.exc.IntegrityError):
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO bills (id, tenant_id, distributor_id, invoice_no, status, confirmed_invoice_key) "
                "VALUES (4, 1, 10, 'INV-001', 'confirmed', '1:10:INV-001')"
            ))


def test_migration_is_idempotent():
    engine = _engine_with_legacy_bills()
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        ops = Operations(ctx)
        migration = _load_migration(ops)
        migration.upgrade()
        conn.commit()

    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        ops = Operations(ctx)
        migration = _load_migration(ops)
        migration.upgrade()
        conn.commit()

    with engine.connect() as conn:
        cols = [r[1] for r in conn.execute(text("PRAGMA table_info(bills)")).fetchall()]
    assert "confirmed_invoice_key" in cols


def test_migration_rejects_existing_duplicate_confirmed_invoices():
    engine = _engine_with_legacy_bills()
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO bills (id, tenant_id, distributor_id, invoice_no, status) "
            "VALUES (1, 1, 10, 'INV-001', 'confirmed'),"
            "       (2, 1, 10, ' inv-001 ', 'confirmed')"
        ))

    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        ops = Operations(ctx)
        migration = _load_migration(ops)
        with pytest.raises(RuntimeError, match="duplicate confirmed bills"):
            migration.upgrade()
