"""Add stock integrity constraints and support atomic stock updates (Issue 3).

Revision ID: 0029
Revises: 0028

Adds a DB-level non-negative guard for medicine stock so concurrent or buggy
writers cannot persist negative inventory. This complements application-level
locked/atomic decrement logic.

Constraints:
  - medicines.current_stock >= 0 (ck_medicines_current_stock_non_negative)

Defensive/idempotent:
  - Skips if medicines table/column missing.
  - Skips if a same-named check constraint already exists.
  - Aborts with a clear error if existing rows violate the invariant.

SQLite note:
  - Uses batch_alter_table so Alembic can recreate the table when needed to add
    a CHECK constraint on SQLite. The application-level schema (Base.metadata)
    is authoritative for SQLite test databases created via create_all.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


TABLE = "medicines"
COLUMN = "current_stock"
CK_NAME = "ck_medicines_current_stock_non_negative"


def _has_table(bind, name: str) -> bool:
    return inspect(bind).has_table(name)


def _has_column(bind, table: str, column: str) -> bool:
    if not _has_table(bind, table):
        return False
    return any(c.get("name") == column for c in inspect(bind).get_columns(table))


def _check_constraint_names(bind, table: str) -> set[str]:
    if not _has_table(bind, table):
        return set()
    try:
        cks = inspect(bind).get_check_constraints(table)
    except Exception:
        return set()
    return {ck.get("name") for ck in cks if ck.get("name")}


def _assert_no_negative_stock(bind) -> None:
    # NULL is treated as invalid here too; application enforces non-null/default.
    row = bind.execute(
        sa.text(
            f"SELECT COUNT(*) FROM {TABLE} "
            f"WHERE {COLUMN} IS NULL OR {COLUMN} < 0"
        )
    ).scalar()
    if row and int(row) > 0:
        raise RuntimeError(
            f"Cannot add {CK_NAME}: found {int(row)} medicines row(s) with NULL/negative {COLUMN}. "
            "Correct data before applying this migration."
        )


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, TABLE) or not _has_column(bind, TABLE, COLUMN):
        return

    _assert_no_negative_stock(bind)

    if CK_NAME in _check_constraint_names(bind, TABLE):
        return

    # Batch mode handles SQLite table recreation requirements.
    try:
        with op.batch_alter_table(TABLE) as batch_op:
            batch_op.create_check_constraint(CK_NAME, f"{COLUMN} >= 0")
    except Exception:
        # Defensive fallback for dialects/inspector quirks: try direct DDL once.
        existing = _check_constraint_names(bind, TABLE)
        if CK_NAME in existing:
            return
        if bind.dialect.name == "sqlite":
            # SQLite cannot add CHECK via ALTER TABLE; batch should have handled it.
            # If it still failed, leave schema creation (tests/create_all) as source of truth.
            return
        op.execute(
            sa.text(
                f"ALTER TABLE {TABLE} ADD CONSTRAINT {CK_NAME} CHECK ({COLUMN} >= 0)"
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, TABLE):
        return
    if CK_NAME not in _check_constraint_names(bind, TABLE):
        # On SQLite batch recreate paths, inspector naming can differ; best-effort only.
        if bind.dialect.name != "sqlite":
            return
    try:
        with op.batch_alter_table(TABLE) as batch_op:
            batch_op.drop_constraint(CK_NAME, type_="check")
    except Exception:
        try:
            if bind.dialect.name != "sqlite":
                op.drop_constraint(CK_NAME, TABLE, type_="check")
        except Exception:
            pass
