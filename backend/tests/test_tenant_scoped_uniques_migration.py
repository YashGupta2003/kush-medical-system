"""Migration tests for tenant-scoped business-key uniqueness (0028)."""
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
    / "alembic" / "versions" / "0028_tenant_scoped_uniques.py"
)

TABLE_SPECS = [
    ("users", "username", "ix_users_username"),
    ("distributors", "name", "ix_distributors_name"),
    ("medicines", "barcode", "ix_medicines_barcode"),
    ("customers", "phone", "ix_customers_phone"),
    ("cold_chain_units", "unit_label", "uq_cold_chain_units_unit_label"),
]


def _load_migration(operations):
    spec = importlib.util.spec_from_file_location("migration_0028", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = operations
    return module


def _engine_with_schema():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


def _run_upgrade(engine):
    with engine.connect() as conn:
        operations = Operations(MigrationContext.configure(conn))
        _load_migration(operations).upgrade()
        conn.commit()


def _drop_unique_indexes_on(engine, table, *column_sets):
    """Drop unique indexes/constraints matching any of the given column sets."""
    wanted = {tuple(cs) for cs in column_sets}
    with engine.begin() as conn:
        insp = inspect(engine)
        # Unique indexes
        for idx in insp.get_indexes(table):
            cols = tuple(idx.get("column_names") or [])
            if cols in wanted and idx.get("unique"):
                conn.execute(text(f'DROP INDEX IF EXISTS "{idx["name"]}"'))
        # SQLite may reflect some uniques as indexes; also try known names later.
    # Re-inspect outside transaction for safety (SQLite DDL autocommits in effect)
    with engine.begin() as conn:
        insp = inspect(engine)
        for idx in insp.get_indexes(table):
            cols = tuple(idx.get("column_names") or [])
            if cols in wanted and idx.get("unique"):
                try:
                    conn.execute(text(f'DROP INDEX IF EXISTS "{idx["name"]}"'))
                except Exception:
                    pass


def _create_legacy_global_uniques(engine):
    with engine.begin() as conn:
        for table, column, legacy_name in TABLE_SPECS:
            # remove composite and any existing unique on bare column to reset
            pass
    # drop composite and bare uniques, then recreate bare legacy uniques
    for table, column, _ in TABLE_SPECS:
        _drop_unique_indexes_on(engine, table, (column,), ("tenant_id", column))
        # also drop any unique index with composite cols regardless of name
        with engine.begin() as conn:
            for idx in inspect(engine).get_indexes(table):
                cols = tuple(idx.get("column_names") or [])
                if idx.get("unique") and (cols == (column,) or cols == ("tenant_id", column)):
                    conn.execute(text(f'DROP INDEX IF EXISTS "{idx["name"]}"'))
    with engine.begin() as conn:
        for table, column, legacy_name in TABLE_SPECS:
            conn.execute(text(
                f'CREATE UNIQUE INDEX IF NOT EXISTS "{legacy_name}" ON "{table}" ("{column}")'
            ))


def _strip_all_target_uniques(engine):
    for table, column, legacy_name in TABLE_SPECS:
        with engine.begin() as conn:
            for idx in inspect(engine).get_indexes(table):
                cols = tuple(idx.get("column_names") or [])
                if idx.get("unique") and (cols == (column,) or cols == ("tenant_id", column)):
                    conn.execute(text(f'DROP INDEX IF EXISTS "{idx["name"]}"'))
        # ensure legacy named index gone too
        with engine.begin() as conn:
            conn.execute(text(f'DROP INDEX IF EXISTS "{legacy_name}"'))


def _insert_two_tenants(conn):
    conn.execute(text(
        "INSERT INTO tenants (id, slug, shop_name, owner_name, email, is_active, email_verified) "
        "VALUES (1, 'one', 'One', 'Owner', 'one@example.com', 1, 0)"
    ))
    conn.execute(text(
        "INSERT INTO tenants (id, slug, shop_name, owner_name, email, is_active, email_verified) "
        "VALUES (2, 'two', 'Two', 'Owner', 'two@example.com', 1, 0)"
    ))


def test_upgrade_converts_global_to_per_tenant_allows_cross_tenant_duplicates():
    engine = _engine_with_schema()
    _create_legacy_global_uniques(engine)

    with engine.begin() as conn:
        _insert_two_tenants(conn)
        # Global uniques allow only one tenant to hold each business key pre-migration.
        conn.execute(text(
            "INSERT INTO users (id, tenant_id, username, password_hash, role, is_active) "
            "VALUES (1, 1, 'staff1', 'x', 'staff', 1), (2, 2, 'staff2', 'x', 'staff', 1)"
        ))
        conn.execute(text(
            "INSERT INTO distributors (id, tenant_id, name) VALUES (1, 1, 'ABC DIST'), (2, 2, 'XYZ DIST')"
        ))
        conn.execute(text(
            "INSERT INTO medicines (id, tenant_id, particulars, normalized_name, current_stock, barcode) "
            "VALUES (1, 1, 'Med A', 'MEDA', 0, 'BAR123'), (2, 2, 'Med B', 'MEDB', 0, 'BAR456')"
        ))
        conn.execute(text(
            "INSERT INTO customers (id, tenant_id, phone) VALUES (1, 1, '9999999999'), (2, 2, '8888888888')"
        ))
        conn.execute(text(
            "INSERT INTO cold_chain_units (id, tenant_id, unit_label, min_temp_c, max_temp_c, is_active) "
            "VALUES (1, 1, 'Fridge 1', 2.0, 8.0, 1), (2, 2, 'Fridge 2', 2.0, 8.0, 1)"
        ))

    _run_upgrade(engine)

    # After upgrade, same business key must be allowed in a different tenant.
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO users (id, tenant_id, username, password_hash, role, is_active) "
            "VALUES (3, 2, 'staff1', 'x', 'staff', 1)"
        ))
        conn.execute(text(
            "INSERT INTO distributors (id, tenant_id, name) VALUES (3, 2, 'ABC DIST')"
        ))
        conn.execute(text(
            "INSERT INTO medicines (id, tenant_id, particulars, normalized_name, current_stock, barcode) "
            "VALUES (3, 2, 'Med C', 'MEDC', 0, 'BAR123')"
        ))
        conn.execute(text(
            "INSERT INTO customers (id, tenant_id, phone) VALUES (3, 2, '9999999999')"
        ))
        conn.execute(text(
            "INSERT INTO cold_chain_units (id, tenant_id, unit_label, min_temp_c, max_temp_c, is_active) "
            "VALUES (3, 2, 'Fridge 1', 2.0, 8.0, 1)"
        ))

    # But duplicates within the same tenant must still be rejected.
    with pytest.raises(Exception):
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO users (id, tenant_id, username, password_hash, role, is_active) "
                "VALUES (4, 1, 'staff1', 'x', 'staff', 1)"
            ))

    inspector = inspect(engine)
    for table, column, _ in TABLE_SPECS:
        uq_indexes = [i for i in inspector.get_indexes(table) if i.get("unique")]
        composite_cols = [tuple(i.get("column_names") or []) for i in uq_indexes]
        assert ("tenant_id", column) in composite_cols, f"missing composite unique for {table}.{column}: {uq_indexes}"


def test_upgrade_rejects_existing_per_tenant_duplicates():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Build a minimal legacy schema (no per-tenant unique on users.username) so a
    # within-tenant duplicate can exist pre-migration; upgrade must abort safely.
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE tenants ("
            "id INTEGER PRIMARY KEY, slug VARCHAR(80) NOT NULL, shop_name VARCHAR(150) NOT NULL, "
            "owner_name VARCHAR(150) NOT NULL, email VARCHAR(150) NOT NULL, "
            "is_active BOOLEAN NOT NULL DEFAULT 1, email_verified BOOLEAN NOT NULL DEFAULT 0"
            ")"
        ))
        conn.execute(text(
            "CREATE TABLE users ("
            "id INTEGER PRIMARY KEY, tenant_id INTEGER, username VARCHAR(50) NOT NULL, "
            "password_hash VARCHAR(255) NOT NULL, full_name VARCHAR(100), "
            "role VARCHAR(10) NOT NULL, is_active BOOLEAN DEFAULT 1, created_at DATETIME, "
            "whatsapp_number VARCHAR(20)"
            ")"
        ))
        conn.execute(text(
            "INSERT INTO tenants (id, slug, shop_name, owner_name, email, is_active, email_verified) "
            "VALUES (1, 'one', 'One', 'Owner', 'one@example.com', 1, 0)"
        ))
        # Insert same-tenant duplicates in a legacy state with no uniqueness on username.
        conn.execute(text(
            "INSERT INTO users (id, tenant_id, username, password_hash, role, is_active) "
            "VALUES (1, 1, 'dup', 'x', 'staff', 1), (2, 1, 'dup', 'x', 'staff', 1)"
        ))

    with pytest.raises(RuntimeError, match="duplicate per-tenant"):
        _run_upgrade(engine)


def test_upgrade_is_idempotent():
    engine = _engine_with_schema()
    _create_legacy_global_uniques(engine)

    with engine.begin() as conn:
        _insert_two_tenants(conn)
        conn.execute(text(
            "INSERT INTO users (id, tenant_id, username, password_hash, role, is_active) "
            "VALUES (1, 1, 'staff1', 'x', 'staff', 1), (2, 2, 'staff2', 'x', 'staff', 1)"
        ))

    _run_upgrade(engine)
    _run_upgrade(engine)  # should not raise

    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM users")).scalar_one() == 2
