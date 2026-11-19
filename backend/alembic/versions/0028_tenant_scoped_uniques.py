"""Scope business-key uniques to tenant_id for multi-tenant correctness.

Revision ID: 0028
Revises: 0027

This migration converts globally-unique business identifiers that must be
unique per shop (tenant) into per-tenant composite unique constraints:

  - users.username           -> (tenant_id, username)
  - distributors.name        -> (tenant_id, name)
  - medicines.barcode        -> (tenant_id, barcode) [nullable barcode]
  - customers.phone          -> (tenant_id, phone)
  - cold_chain_units.unit_label -> (tenant_id, unit_label)

It intentionally leaves globally-unique/system identifiers global:
  tenants.slug/email, refresh_tokens.token_hash, audit_ledger.entry_hash,
and cross-tenant/global reference/aggregate uniques (batch alerts, regional
alerts/heatmaps, clinical reference tables, medicine_batches.bill_item_id).

Defensive/idempotent:
  - Drops known legacy global unique indexes/constraints when present.
  - Creates composite uniques and supporting non-unique indexes when missing.
  - Aborts with an explicit error if duplicate business keys exist within the
    same tenant, because automatic disambiguation would be unsafe for
    authentication, POS lookup, or customer credit data.

SQLite note:
  - SQLite cannot ALTER constraints in place; for SQLite the model-level
    schema (create_all in tests) is authoritative and this migration is a
    no-op beyond duplicate detection.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


TABLE_SPECS = [
    {
        "table": "users",
        "column": "username",
        "old_unique_indexes": ("ix_users_username",),
        "old_unique_constraints": ("uq_users_username", "users_username_key"),
        "new_constraint": "uq_users_tenant_username",
        "new_index": "ix_users_tenant_username",
    },
    {
        "table": "distributors",
        "column": "name",
        "old_unique_indexes": ("ix_distributors_name",),
        "old_unique_constraints": ("uq_distributors_name", "distributors_name_key"),
        "new_constraint": "uq_distributors_tenant_name",
        "new_index": "ix_distributors_tenant_name",
    },
    {
        "table": "medicines",
        "column": "barcode",
        "old_unique_indexes": ("ix_medicines_barcode",),
        "old_unique_constraints": ("uq_medicines_barcode", "medicines_barcode_key"),
        "new_constraint": "uq_medicines_tenant_barcode",
        "new_index": "ix_medicines_tenant_barcode",
        "nullable": True,
    },
    {
        "table": "customers",
        "column": "phone",
        "old_unique_indexes": ("ix_customers_phone",),
        "old_unique_constraints": ("uq_customers_phone", "customers_phone_key"),
        "new_constraint": "uq_customers_tenant_phone",
        "new_index": "ix_customers_tenant_phone",
    },
    {
        "table": "cold_chain_units",
        "column": "unit_label",
        "old_unique_indexes": ("ix_cold_chain_units_unit_label",),
        "old_unique_constraints": ("uq_cold_chain_units_unit_label", "cold_chain_units_unit_label_key"),
        "new_constraint": "uq_cold_chain_units_tenant_label",
        "new_index": "ix_cold_chain_units_tenant_label",
    },
]


def _has_table(bind, name: str) -> bool:
    return inspect(bind).has_table(name)


def _unique_indexes(bind, table: str):
    if not _has_table(bind, table):
        return {}
    insp = inspect(bind)
    result = {}
    for idx in insp.get_indexes(table):
        if idx.get("unique") and idx.get("name"):
            result[idx["name"]] = idx
    return result


def _unique_constraints(bind, table: str):
    if not _has_table(bind, table):
        return {}
    insp = inspect(bind)
    result = {}
    for uc in insp.get_unique_constraints(table):
        if uc.get("name"):
            result[uc["name"]] = uc
    return result


def _non_unique_indexes(bind, table: str):
    if not _has_table(bind, table):
        return {}
    insp = inspect(bind)
    result = {}
    for idx in insp.get_indexes(table):
        if not idx.get("unique") and idx.get("name"):
            result[idx["name"]] = idx
    return result


def _assert_no_per_tenant_duplicates(bind, spec):
    table = spec["table"]
    column = spec["column"]
    if not _has_table(bind, table):
        return
    nullable = spec.get("nullable", False)
    where = f"WHERE {column} IS NOT NULL" if nullable else ""
    # NULL tenant_id duplicates are also unsafe/unscoped; include them in grouping.
    sql = sa.text(
        f"""
        SELECT tenant_id, {column}, COUNT(*) AS cnt
        FROM {table}
        {where}
        GROUP BY tenant_id, {column}
        HAVING COUNT(*) > 1
        """
    )
    rows = bind.execute(sql).fetchall()
    if rows:
        sample = rows[:5]
        raise RuntimeError(
            f"Cannot apply 0028: duplicate per-tenant values found in {table}.{column} "
            f"(sample tenant_id/value/count: {sample}). Resolve duplicates manually "
            f"before rerunning this migration."
        )


def _drop_legacy_global_uniques(bind, spec):
    table = spec["table"]
    column = spec["column"]
    dialect = bind.dialect.name

    # Drop known/legacy unique indexes on the bare column.
    uidx = _unique_indexes(bind, table)
    for name in spec.get("old_unique_indexes", ()): 
        if name in uidx:
            op.drop_index(name, table_name=table)
    # Also drop any other unique index whose columns are exactly [column].
    uidx = _unique_indexes(bind, table)
    for name, idx in list(uidx.items()):
        cols = idx.get("column_names") or []
        if cols == [column]:
            op.drop_index(name, table_name=table)

    # Drop known/legacy unique constraints on the bare column.
    ucs = _unique_constraints(bind, table)
    for name in spec.get("old_unique_constraints", ()): 
        if name in ucs:
            if dialect == "mysql":
                # In MySQL a UNIQUE constraint is backed by an index; DROP INDEX is reliable.
                op.drop_index(name, table_name=table)
            else:
                try:
                    op.drop_constraint(name, table_name=table, type_="unique")
                except Exception:
                    pass
    ucs = _unique_constraints(bind, table)
    for name, uc in list(ucs.items()):
        cols = uc.get("column_names") or []
        if cols == [column]:
            if dialect == "mysql":
                op.drop_index(name, table_name=table)
            else:
                try:
                    op.drop_constraint(name, table_name=table, type_="unique")
                except Exception:
                    pass


def _ensure_composite_unique(bind, spec):
    table = spec["table"]
    column = spec["column"]
    new_name = spec["new_constraint"]

    ucs = _unique_constraints(bind, table)
    # If an equivalent composite unique already exists under any name, keep it.
    for uc in ucs.values():
        if (uc.get("column_names") or []) == ["tenant_id", column]:
            return
    uidx = _unique_indexes(bind, table)
    for idx in uidx.values():
        if (idx.get("column_names") or []) == ["tenant_id", column]:
            return

    # Avoid name collisions.
    if new_name in ucs or new_name in uidx:
        return

    try:
        with op.batch_alter_table(table) as batch_op:
            batch_op.create_unique_constraint(new_name, ["tenant_id", column])
    except Exception:
        # Fallback: create a unique index (equivalent enforcement for most engines).
        try:
            op.create_index(new_name, table, ["tenant_id", column], unique=True)
        except Exception:
            pass


def _ensure_supporting_index(bind, spec):
    table = spec["table"]
    column = spec["column"]
    index_name = spec["new_index"]
    if not _has_table(bind, table):
        return
    existing = {**_unique_indexes(bind, table), **_non_unique_indexes(bind, table)}
    for idx in existing.values():
        cols = idx.get("column_names") or []
        if cols == [column] or cols[:2] == ["tenant_id", column]:
            # An index already supports lookups on this key.
            return
    if index_name in existing:
        return
    try:
        op.create_index(index_name, table, ["tenant_id", column], unique=False)
    except Exception:
        pass


def upgrade() -> None:
    bind = op.get_bind()
    # Always fail fast on unsafe duplicate business keys before structural changes.
    for spec in TABLE_SPECS:
        if _has_table(bind, spec["table"]):
            _assert_no_per_tenant_duplicates(bind, spec)

    if bind.dialect.name == "sqlite":
        # SQLite has limited ALTER TABLE support; perform best-effort index-level
        # changes for legacy unique indexes (the form used by prior migrations).
        for spec in TABLE_SPECS:
            if not _has_table(bind, spec["table"]):
                continue
            table = spec["table"]
            column = spec["column"]
            # Drop legacy global unique indexes if present.
            uidx = _unique_indexes(bind, table)
            for name in spec.get("old_unique_indexes", ()):
                if name in uidx:
                    try:
                        op.drop_index(name, table_name=table)
                    except Exception:
                        pass
            uidx = _unique_indexes(bind, table)
            for name, idx in list(uidx.items()):
                if (idx.get("column_names") or []) == [column]:
                    try:
                        op.drop_index(name, table_name=table)
                    except Exception:
                        pass
            # Create composite unique index when missing (enforces per-tenant uniqueness).
            existing_uidx = _unique_indexes(bind, table)
            has_composite = any(
                (i.get("column_names") or []) == ["tenant_id", column]
                for i in existing_uidx.values()
            )
            if not has_composite:
                try:
                    op.create_index(
                        spec["new_constraint"], table, ["tenant_id", column], unique=True
                    )
                except Exception:
                    pass
        return

    for spec in TABLE_SPECS:
        if not _has_table(bind, spec["table"]):
            continue
        _drop_legacy_global_uniques(bind, spec)
        _ensure_composite_unique(bind, spec)
        _ensure_supporting_index(bind, spec)


def downgrade() -> None:
    bind = op.get_bind()
    for spec in TABLE_SPECS:
        table = spec["table"]
        column = spec["column"]
        if not _has_table(bind, table):
            continue

        # Drop composite unique/index forms (index form on SQLite, constraint/index on others).
        for name in (spec["new_constraint"], spec["new_index"]):
            try:
                if bind.dialect.name != "sqlite":
                    ucs = _unique_constraints(bind, table)
                    if name in ucs:
                        if bind.dialect.name == "mysql":
                            op.drop_index(name, table_name=table)
                        else:
                            op.drop_constraint(name, table_name=table, type_="unique")
                        continue
            except Exception:
                pass
            try:
                idxs = {**_unique_indexes(bind, table), **_non_unique_indexes(bind, table)}
                if name in idxs:
                    op.drop_index(name, table_name=table)
            except Exception:
                pass

        if bind.dialect.name == "sqlite":
            # Best-effort restoration of legacy global unique indexes.
            old = (spec.get("old_unique_indexes") or (None,))[0]
            if not old:
                continue
            uidx = _unique_indexes(bind, table)
            already = any((i.get("column_names") or []) == [column] for i in uidx.values())
            if already:
                continue
            try:
                op.create_index(old, table, [column], unique=True)
            except Exception:
                pass
            continue

        # Restore a global unique index where previously expected.
        old = (spec.get("old_unique_indexes") or (None,))[0]
        if not old:
            continue
        uidx = _unique_indexes(bind, table)
        already = any((i.get("column_names") or []) == [column] for i in uidx.values())
        if already:
            continue
        try:
            op.create_index(old, table, [column], unique=True)
        except Exception:
            pass
