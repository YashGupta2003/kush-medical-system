"""Migration tests for the global clinical-reference tables (0027)."""
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
    / "alembic" / "versions" / "0027_clinical_reference_tables.py"
)


def _load_migration(operations):
    spec = importlib.util.spec_from_file_location("migration_0027", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = operations
    return module


def _engine_without_clinical_tables():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    models.DrugInteraction.__table__.drop(engine, checkfirst=True)
    models.SaltCondition.__table__.drop(engine, checkfirst=True)
    return engine


def test_migration_creates_global_tables_with_unique_keys():
    engine = _engine_without_clinical_tables()

    with engine.connect() as conn:
        operations = Operations(MigrationContext.configure(conn))
        _load_migration(operations).upgrade()
        conn.commit()

    inspector = inspect(engine)
    assert {"salt_conditions", "drug_interactions"}.issubset(inspector.get_table_names())
    for table in ("salt_conditions", "drug_interactions"):
        columns = {column["name"] for column in inspector.get_columns(table)}
        assert "tenant_id" not in columns
    assert any(
        constraint["name"] == "uq_salt_conditions_salt_name"
        for constraint in inspector.get_unique_constraints("salt_conditions")
    )
    assert any(
        constraint["name"] == "uq_drug_interactions_salt_pair"
        for constraint in inspector.get_unique_constraints("drug_interactions")
    )


def test_migration_is_idempotent_and_reversible():
    engine = _engine_without_clinical_tables()

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
    assert "salt_conditions" not in tables
    assert "drug_interactions" not in tables
