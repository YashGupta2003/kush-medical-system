"""Harden bill confirmation: DB guard for confirmed-invoice uniqueness (Issue 4).

Revision ID: 0030
Revises: 0029

Adds `bills.confirmed_invoice_key` and a unique constraint so that concurrent or
replayed confirmations cannot persist duplicate confirmed invoices for the same
tenant + distributor + normalized invoice number.

Key format (when dedup-able): "{tenant_id}:{distributor_id}:{NORMALIZED_INVOICE_NO}"
Normalization matches duplicate_service.normalize_invoice_no: strip + upper, empty -> None.
When any component is missing (no tenant/distributor/invoice), key is NULL and no
uniqueness is enforced (invoice cannot be meaningfully deduplicated).

Defensive/idempotent:
  - Adds column if missing.
  - Backfills keys for confirmed bills; aborts if existing confirmed duplicates
    would violate uniqueness (manual resolution required).
  - Creates unique constraint/index if missing.

SQLite note:
  - Uses batch_alter_table for column/constraint changes where appropriate.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None

TABLE = "bills"
COLUMN = "confirmed_invoice_key"
UQ_NAME = "uq_bills_confirmed_invoice_key"


def _normalize_invoice_no(value):
    if value is None:
        return None
    cleaned = str(value).strip().upper()
    return cleaned if cleaned else None


def _key(tenant_id, distributor_id, invoice_no):
    norm = _normalize_invoice_no(invoice_no)
    if tenant_id is None or distributor_id is None or norm is None:
        return None
    return f"{tenant_id}:{distributor_id}:{norm}"


def _has_table(bind, name: str) -> bool:
    return inspect(bind).has_table(name)


def _has_column(bind, table: str, column: str) -> bool:
    if not _has_table(bind, table):
        return False
    return any(c.get("name") == column for c in inspect(bind).get_columns(table))


def _unique_names(bind, table: str) -> set[str]:
    if not _has_table(bind, table):
        return set()
    insp = inspect(bind)
    names = set()
    try:
        for uq in insp.get_unique_constraints(table):
            if uq.get("name"):
                names.add(uq["name"])
    except Exception:
        pass
    try:
        for idx in insp.get_indexes(table):
            if idx.get("unique") and idx.get("name"):
                names.add(idx["name"])
    except Exception:
        pass
    return names


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, TABLE):
        return

    # 1) Add column if missing
    if not _has_column(bind, TABLE, COLUMN):
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table(TABLE) as batch_op:
                batch_op.add_column(sa.Column(COLUMN, sa.String(length=255), nullable=True))
        else:
            op.add_column(TABLE, sa.Column(COLUMN, sa.String(length=255), nullable=True))

    # 2) Backfill confirmed bill keys and detect conflicts
    if _has_column(bind, TABLE, COLUMN):
        rows = bind.execute(
            sa.text(
                f"SELECT id, tenant_id, distributor_id, invoice_no, status "
                f"FROM {TABLE} WHERE status = :status"
            ),
            {"status": "confirmed"},
        ).mappings().all()

        groups = {}
        for row in rows:
            k = _key(row.get("tenant_id"), row.get("distributor_id"), row.get("invoice_no"))
            if k is None:
                continue
            groups.setdefault(k, []).append(row["id"])

        conflicts = {k: ids for k, ids in groups.items() if len(ids) > 1}
        if conflicts:
            sample = list(conflicts.items())[:5]
            raise RuntimeError(
                "Cannot add unique confirmed-invoice guard: existing duplicate confirmed bills found "
                f"for keys (sample): {sample}. Resolve duplicates before migration."
            )

        # Apply backfill idempotently.
        for row in rows:
            k = _key(row.get("tenant_id"), row.get("distributor_id"), row.get("invoice_no"))
            # Set key for dedup-able confirmed bills; clear for others (idempotent).
            bind.execute(
                sa.text(f"UPDATE {TABLE} SET {COLUMN} = :key WHERE id = :id"),
                {"key": k, "id": row["id"]},
            )

    # 3) Create unique constraint/index if missing
    if UQ_NAME not in _unique_names(bind, TABLE):
        try:
            if bind.dialect.name == "sqlite":
                with op.batch_alter_table(TABLE) as batch_op:
                    batch_op.create_unique_constraint(UQ_NAME, [COLUMN])
            elif bind.dialect.name == "mysql":
                op.create_index(UQ_NAME, TABLE, [COLUMN], unique=True)
            else:
                op.create_unique_constraint(UQ_NAME, TABLE, [COLUMN])
        except Exception:
            if UQ_NAME not in _unique_names(bind, TABLE):
                # Best-effort fallback
                try:
                    op.create_index(UQ_NAME, TABLE, [COLUMN], unique=True)
                except Exception:
                    pass


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, TABLE):
        return

    # Drop unique/index/constraint if present
    for name in (UQ_NAME,):
        try:
            if name in _unique_names(bind, TABLE):
                # Try constraint drop on non-mysql, index drop on mysql/sqlite index form
                if bind.dialect.name == "mysql":
                    op.drop_index(name, table_name=TABLE)
                else:
                    try:
                        op.drop_constraint(name, TABLE, type_="unique")
                    except Exception:
                        op.drop_index(name, table_name=TABLE)
        except Exception:
            try:
                op.drop_index(name, table_name=TABLE)
            except Exception:
                pass

    if _has_column(bind, TABLE, COLUMN):
        try:
            if bind.dialect.name == "sqlite":
                with op.batch_alter_table(TABLE) as batch_op:
                    batch_op.drop_column(COLUMN)
            else:
                op.drop_column(TABLE, COLUMN)
        except Exception:
            pass
