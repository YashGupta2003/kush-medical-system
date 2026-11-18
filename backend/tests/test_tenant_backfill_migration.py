"""Tests for the NULL-tenant backfill migration (0025)."""
import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic" / "versions" / "0025_backfill_tenant_ids.py"
)


def _load_migration(operations):
    spec = importlib.util.spec_from_file_location("migration_0025", MIGRATION_PATH)
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


def test_backfill_assigns_single_tenant_to_all_null_rows():
    engine = _engine_with_schema()
    session = sessionmaker(bind=engine)()

    tenant = models.Tenant(
        slug="only-shop", shop_name="Only Shop", owner_name="Owner",
        email="only@example.com",
    )
    session.add(tenant)
    session.flush()

    medicine = models.Medicine(
        tenant_id=None, particulars="LEGACY", normalized_name="LEGACY",
    )
    user = models.User(
        tenant_id=None, username="legacy-owner", password_hash="x",
        role="owner", is_active=True,
    )
    derived_edge = models.GraphEdge(
        tenant_id=None, source_type="medicine", source_id="1",
        edge_type="CONTAINS", target_type="salt", target_id="PARACETAMOL",
    )
    curated_edge = models.GraphEdge(
        tenant_id=None, source_type="salt", source_id="PARACETAMOL",
        edge_type="INTERACTS_WITH", target_type="salt", target_id="IBUPROFEN",
    )
    session.add_all([medicine, user, derived_edge, curated_edge])
    session.commit()
    tenant_id = tenant.id
    medicine_id, user_id = medicine.id, user.id
    derived_id, curated_id = derived_edge.id, curated_edge.id

    with engine.connect() as conn:
        operations = Operations(MigrationContext.configure(conn))
        _load_migration(operations).upgrade()
        conn.commit()

    session.expunge_all()
    assert session.get(models.Medicine, medicine_id).tenant_id == tenant_id
    assert session.get(models.User, user_id).tenant_id == tenant_id
    assert session.get(models.GraphEdge, derived_id).tenant_id == tenant_id
    # Curated reference data is global by design and must stay NULL.
    assert session.get(models.GraphEdge, curated_id).tenant_id is None


def test_backfill_uses_parent_tenant_in_multi_tenant_database():
    engine = _engine_with_schema()
    session = sessionmaker(bind=engine)()

    first = models.Tenant(
        slug="one", shop_name="One", owner_name="Owner", email="one@example.com",
    )
    second = models.Tenant(
        slug="two", shop_name="Two", owner_name="Owner", email="two@example.com",
    )
    session.add_all([first, second])
    session.flush()

    medicine = models.Medicine(
        tenant_id=first.id, particulars="MINE", normalized_name="MINE",
    )
    session.add(medicine)
    session.flush()
    legacy_item = models.BillItem(
        tenant_id=None, bill_id=None, medicine_id=medicine.id,
        raw_name="LEGACY",
    )
    # bill_id is NOT NULL in a real MySQL schema; SQLite in the test schema
    # enforces it, so create a parent bill and point the item at it.
    bill = models.Bill(tenant_id=first.id, invoice_no="LEGACY-INV", status="confirmed")
    session.add(bill)
    session.flush()
    legacy_item.bill_id = bill.id
    session.add(legacy_item)
    session.commit()
    tenant_id = first.id
    item_id = legacy_item.id

    with engine.connect() as conn:
        operations = Operations(MigrationContext.configure(conn))
        _load_migration(operations).upgrade()
        conn.commit()

    session.expunge_all()
    assert session.get(models.BillItem, item_id).tenant_id == tenant_id


def test_backfill_is_idempotent():
    engine = _engine_with_schema()
    session = sessionmaker(bind=engine)()

    tenant = models.Tenant(
        slug="only-shop", shop_name="Only Shop", owner_name="Owner",
        email="only@example.com",
    )
    medicine = models.Medicine(
        tenant_id=None, particulars="LEGACY", normalized_name="LEGACY",
    )
    session.add_all([tenant, medicine])
    session.commit()
    tenant_id = tenant.id
    medicine_id = medicine.id

    for _ in range(2):
        with engine.connect() as conn:
            operations = Operations(MigrationContext.configure(conn))
            _load_migration(operations).upgrade()
            conn.commit()

    session.expunge_all()
    assert session.get(models.Medicine, medicine_id).tenant_id == tenant_id
