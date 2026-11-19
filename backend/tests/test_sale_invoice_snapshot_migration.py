"""Migration tests for sale invoice/snapshot schema (0031)."""
import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic" / "versions" / "0031_sale_invoices_and_snapshots.py"
)


def _load_migration(operations):
    spec = importlib.util.spec_from_file_location("migration_0031", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = operations
    return module


def _engine_with_legacy_sales():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE tenants (id INTEGER PRIMARY KEY)"))
        conn.execute(text("CREATE TABLE medicines (id INTEGER PRIMARY KEY, particulars VARCHAR(255), composition VARCHAR(500), mrp NUMERIC(10,2), net_rate NUMERIC(10,2))"))
        conn.execute(text("CREATE TABLE customers (id INTEGER PRIMARY KEY)"))
        conn.execute(text(
            "CREATE TABLE sales ("
            "id INTEGER PRIMARY KEY, tenant_id INTEGER, medicine_id INTEGER, qty_sold NUMERIC(10,2), "
            "sold_at DATETIME, customer_id INTEGER)"
        ))
        conn.execute(text("INSERT INTO tenants (id) VALUES (1)"))
        conn.execute(text("INSERT INTO medicines (id, particulars, composition, mrp, net_rate) VALUES (10, 'PARA 500', 'Paracetamol', 20.00, 12.50)"))
        conn.execute(text("INSERT INTO sales (id, tenant_id, medicine_id, qty_sold, sold_at, customer_id) VALUES (1, 1, 10, 2, '2026-01-01 10:00:00', NULL)"))
    return engine


def _upgrade(engine):
    with engine.begin() as conn:
        migration = _load_migration(Operations(MigrationContext.configure(conn)))
        migration.upgrade()


def test_upgrade_creates_sale_invoice_tables_and_snapshot_columns():
    engine = _engine_with_legacy_sales()
    _upgrade(engine)

    insp = inspect(engine)
    assert insp.has_table("sale_invoices")
    assert insp.has_table("sale_invoice_counters")

    sale_cols = {c["name"] for c in insp.get_columns("sales")}
    assert "sale_invoice_id" in sale_cols
    assert "unit_mrp_snapshot" in sale_cols
    assert "unit_cost_snapshot" in sale_cols
    assert "gst_pct_snapshot" in sale_cols
    assert "line_subtotal" in sale_cols
    assert "line_tax_amount" in sale_cols
    assert "line_total" in sale_cols
    assert "line_profit" in sale_cols


def test_upgrade_backfills_legacy_sale_into_invoice_and_snapshots():
    engine = _engine_with_legacy_sales()
    _upgrade(engine)

    with engine.connect() as conn:
        sale = conn.execute(text(
            "SELECT sale_invoice_id, unit_mrp_snapshot, unit_cost_snapshot, line_total, line_profit "
            "FROM sales WHERE id = 1"
        )).mappings().one()
        assert sale["sale_invoice_id"] is not None
        assert float(sale["unit_mrp_snapshot"]) == 20.0
        assert float(sale["unit_cost_snapshot"]) == 12.5
        assert float(sale["line_total"]) == 40.0
        assert float(sale["line_profit"]) == 15.0

        inv = conn.execute(text(
            "SELECT invoice_number, total_amount, total_profit FROM sale_invoices WHERE id = :id"
        ), {"id": sale["sale_invoice_id"]}).mappings().one()
        assert "LEGACY-SALE-" in inv["invoice_number"]
        assert float(inv["total_amount"]) == 40.0
        assert float(inv["total_profit"]) == 15.0


def test_upgrade_is_idempotent_for_tables_columns_and_backfill():
    engine = _engine_with_legacy_sales()
    _upgrade(engine)
    _upgrade(engine)

    insp = inspect(engine)
    assert insp.has_table("sale_invoices")
    with engine.connect() as conn:
        sale_count = conn.execute(text("SELECT COUNT(*) FROM sales")).scalar_one()
        inv_count = conn.execute(text("SELECT COUNT(*) FROM sale_invoices")).scalar_one()
        assert sale_count == 1
        assert inv_count == 1
