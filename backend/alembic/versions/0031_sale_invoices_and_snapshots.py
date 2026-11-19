"""Add sale invoices, invoice counters, and sale line snapshots (Issue 5).

Revision ID: 0031
Revises: 0030

Persists tenant-scoped sale invoice headers and per-sale-line pricing/GST/profit
snapshots captured at sale time. Legacy sale rows are backfilled defensively so
existing data remains queryable.

Defensive/idempotent:
  - Creates tables/columns/indexes only when missing.
  - Backfills invoice headers/links and snapshot columns for legacy sales.
  - Seeds per-tenant sale invoice counters from existing invoice numbers.

Notes:
  - Money/quantity snapshot columns use Numeric for cross-db consistency.
  - Unique/index guards are created in MySQL/SQLite-safe forms where practical.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import re

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


SALE_INVOICES = "sale_invoices"
SALE_INVOICE_COUNTERS = "sale_invoice_counters"
SALES = "sales"

UQ_SALE_INVOICE_TENANT_NUMBER = "uq_sale_invoices_tenant_invoice_number"
IX_SALE_INVOICE_TENANT_NUMBER = "ix_sale_invoices_tenant_invoice_number"
UQ_SALE_COUNTER_TENANT = "uq_sale_invoice_counters_tenant_id"


def _has_table(bind, name: str) -> bool:
    return inspect(bind).has_table(name)


def _has_column(bind, table: str, column: str) -> bool:
    if not _has_table(bind, table):
        return False
    return any(c.get("name") == column for c in inspect(bind).get_columns(table))


def _index_names(bind, table: str) -> set[str]:
    if not _has_table(bind, table):
        return set()
    try:
        return {idx.get("name") for idx in inspect(bind).get_indexes(table) if idx.get("name")}
    except Exception:
        return set()


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


def _fk_names(bind, table: str) -> set[str]:
    if not _has_table(bind, table):
        return set()
    try:
        return {fk.get("name") for fk in inspect(bind).get_foreign_keys(table) if fk.get("name")}
    except Exception:
        return set()


def _d(value) -> Decimal:
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _q2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _invoice_seq(invoice_number) -> int | None:
    if not invoice_number:
        return None
    m = re.search(r"(\d+)$", str(invoice_number))
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def _create_sale_invoices(bind) -> None:
    if _has_table(bind, SALE_INVOICES):
        return
    op.create_table(
        SALE_INVOICES,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("invoice_number", sa.String(length=64), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=True),
        sa.Column("payment_mode", sa.String(length=20), nullable=False, server_default="cash"),
        sa.Column("subtotal_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_profit", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("sold_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_sale_invoices_tenant_id", SALE_INVOICES, ["tenant_id"], unique=False)
    op.create_index("ix_sale_invoices_customer_id", SALE_INVOICES, ["customer_id"], unique=False)
    op.create_index(IX_SALE_INVOICE_TENANT_NUMBER, SALE_INVOICES, ["tenant_id", "invoice_number"], unique=True)


def _create_sale_invoice_counters(bind) -> None:
    if _has_table(bind, SALE_INVOICE_COUNTERS):
        return
    op.create_table(
        SALE_INVOICE_COUNTERS,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("last_number", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_sale_invoice_counters_tenant_id", SALE_INVOICE_COUNTERS, ["tenant_id"], unique=True)


def _add_sales_columns(bind) -> None:
    if not _has_table(bind, SALES):
        return
    cols = [
        ("sale_invoice_id", sa.Column("sale_invoice_id", sa.Integer(), nullable=True)),
        ("medicine_name_snapshot", sa.Column("medicine_name_snapshot", sa.String(length=255), nullable=True)),
        ("medicine_composition_snapshot", sa.Column("medicine_composition_snapshot", sa.String(length=500), nullable=True)),
        ("unit_mrp_snapshot", sa.Column("unit_mrp_snapshot", sa.Numeric(10, 2), nullable=True)),
        ("unit_cost_snapshot", sa.Column("unit_cost_snapshot", sa.Numeric(10, 2), nullable=True)),
        ("gst_pct_snapshot", sa.Column("gst_pct_snapshot", sa.Numeric(5, 2), nullable=True)),
        ("line_subtotal", sa.Column("line_subtotal", sa.Numeric(12, 2), nullable=True)),
        ("line_tax_amount", sa.Column("line_tax_amount", sa.Numeric(12, 2), nullable=True)),
        ("line_total", sa.Column("line_total", sa.Numeric(12, 2), nullable=True)),
        ("line_profit", sa.Column("line_profit", sa.Numeric(12, 2), nullable=True)),
    ]
    existing = {c.get("name") for c in inspect(bind).get_columns(SALES)}
    for name, col in cols:
        if name not in existing:
            op.add_column(SALES, col)
    # Index/FK best-effort
    try:
        if "ix_sales_sale_invoice_id" not in _index_names(bind, SALES) and _has_column(bind, SALES, "sale_invoice_id"):
            op.create_index("ix_sales_sale_invoice_id", SALES, ["sale_invoice_id"], unique=False)
    except Exception:
        pass


def _backfill_legacy_sales(bind) -> None:
    if not (_has_table(bind, SALES) and _has_table(bind, SALE_INVOICES)):
        return
    if not _has_column(bind, SALES, "sale_invoice_id"):
        return

    legacy_rows = bind.execute(
        sa.text(
            f"SELECT s.id, s.tenant_id, s.medicine_id, s.qty_sold, s.sold_at, s.customer_id, "
            f"m.particulars AS medicine_name, m.composition AS medicine_composition, "
            f"m.mrp AS mrp, m.net_rate AS net_rate "
            f"FROM {SALES} s LEFT JOIN medicines m ON m.id = s.medicine_id "
            f"WHERE s.sale_invoice_id IS NULL ORDER BY s.id ASC"
        )
    ).mappings().all()

    existing_nums = set()
    try:
        rows = bind.execute(sa.text(f"SELECT tenant_id, invoice_number FROM {SALE_INVOICES}")).mappings().all()
        for r in rows:
            existing_nums.add((r.get("tenant_id"), r.get("invoice_number")))
    except Exception:
        pass

    now = datetime.now(timezone.utc)
    for row in legacy_rows:
        sale_id = row["id"]
        tenant_id = row.get("tenant_id")
        invoice_number = f"LEGACY-SALE-{tenant_id if tenant_id is not None else 'GLOBAL'}-{sale_id}"
        if (tenant_id, invoice_number) not in existing_nums:
            bind.execute(
                sa.text(
                    f"INSERT INTO {SALE_INVOICES} "
                    "(tenant_id, invoice_number, customer_id, payment_mode, subtotal_amount, tax_amount, total_amount, total_profit, sold_at, created_at) "
                    "VALUES (:tenant_id, :invoice_number, :customer_id, 'cash', 0, 0, 0, 0, :sold_at, :created_at)"
                ),
                {
                    "tenant_id": tenant_id,
                    "invoice_number": invoice_number,
                    "customer_id": row.get("customer_id"),
                    "sold_at": row.get("sold_at") or now,
                    "created_at": row.get("sold_at") or now,
                },
            )
            existing_nums.add((tenant_id, invoice_number))

        inv_id = bind.execute(
            sa.text(
                f"SELECT id FROM {SALE_INVOICES} WHERE invoice_number = :invoice_number "
                f"AND ((tenant_id = :tenant_id) OR (tenant_id IS NULL AND :tenant_id IS NULL)) "
                f"ORDER BY id DESC LIMIT 1"
            ),
            {"invoice_number": invoice_number, "tenant_id": tenant_id},
        ).scalar()

        qty = _d(row.get("qty_sold"))
        mrp = _d(row.get("mrp"))
        cost = _d(row.get("net_rate"))
        gst = Decimal("0.00")
        line_total = _q2(mrp * qty)
        line_tax = Decimal("0.00")
        line_subtotal = line_total
        line_profit = _q2((mrp - cost) * qty)

        bind.execute(
            sa.text(
                f"UPDATE {SALES} SET "
                "sale_invoice_id = :inv_id, "
                "medicine_name_snapshot = COALESCE(medicine_name_snapshot, :mname), "
                "medicine_composition_snapshot = COALESCE(medicine_composition_snapshot, :mcomp), "
                "unit_mrp_snapshot = COALESCE(unit_mrp_snapshot, :mrp), "
                "unit_cost_snapshot = COALESCE(unit_cost_snapshot, :cost), "
                "gst_pct_snapshot = COALESCE(gst_pct_snapshot, :gst), "
                "line_subtotal = COALESCE(line_subtotal, :line_subtotal), "
                "line_tax_amount = COALESCE(line_tax_amount, :line_tax), "
                "line_total = COALESCE(line_total, :line_total), "
                "line_profit = COALESCE(line_profit, :line_profit) "
                "WHERE id = :sid"
            ),
            {
                "inv_id": inv_id,
                "mname": row.get("medicine_name"),
                "mcomp": row.get("medicine_composition"),
                "mrp": str(_q2(mrp)),
                "cost": str(_q2(cost)),
                "gst": str(_q2(gst)),
                "line_subtotal": str(line_subtotal),
                "line_tax": str(line_tax),
                "line_total": str(line_total),
                "line_profit": str(line_profit),
                "sid": sale_id,
            },
        )

        if inv_id is not None:
            bind.execute(
                sa.text(
                    f"UPDATE {SALE_INVOICES} SET "
                    "subtotal_amount = :subtotal, tax_amount = :tax, total_amount = :total, total_profit = :profit "
                    "WHERE id = :inv_id"
                ),
                {
                    "subtotal": str(line_subtotal),
                    "tax": str(line_tax),
                    "total": str(line_total),
                    "profit": str(line_profit),
                    "inv_id": inv_id,
                },
            )

    # Seed counters from existing non-legacy sale invoice numbers per tenant.
    if _has_table(bind, SALE_INVOICE_COUNTERS):
        try:
            rows = bind.execute(
                sa.text(f"SELECT tenant_id, invoice_number FROM {SALE_INVOICES} WHERE tenant_id IS NOT NULL")
            ).mappings().all()
            max_by_tenant = {}
            for r in rows:
                tid = r.get("tenant_id")
                if tid is None:
                    continue
                seq = _invoice_seq(r.get("invoice_number"))
                if seq is None:
                    continue
                if str(r.get("invoice_number") or "").startswith("LEGACY-SALE-"):
                    continue
                max_by_tenant[tid] = max(max_by_tenant.get(tid, 0), seq)
            for tid, seq in max_by_tenant.items():
                existing = bind.execute(
                    sa.text(f"SELECT id FROM {SALE_INVOICE_COUNTERS} WHERE tenant_id = :tid"),
                    {"tid": tid},
                ).scalar()
                if existing is None:
                    bind.execute(
                        sa.text(
                            f"INSERT INTO {SALE_INVOICE_COUNTERS} (tenant_id, last_number, updated_at) "
                            "VALUES (:tid, :seq, :now)"
                        ),
                        {"tid": tid, "seq": seq, "now": now},
                    )
                else:
                    bind.execute(
                        sa.text(
                            f"UPDATE {SALE_INVOICE_COUNTERS} SET last_number = CASE WHEN last_number < :seq THEN :seq ELSE last_number END "
                            "WHERE tenant_id = :tid"
                        ),
                        {"tid": tid, "seq": seq},
                    )
        except Exception:
            pass


def upgrade() -> None:
    bind = op.get_bind()
    _create_sale_invoices(bind)
    _create_sale_invoice_counters(bind)
    _add_sales_columns(bind)
    # Backfill after schema present
    _backfill_legacy_sales(bind)

    # Ensure uniqueness on sale invoice number per tenant where possible.
    try:
        if _has_table(bind, SALE_INVOICES) and IX_SALE_INVOICE_TENANT_NUMBER not in _index_names(bind, SALE_INVOICES) and UQ_SALE_INVOICE_TENANT_NUMBER not in _unique_names(bind, SALE_INVOICES):
            op.create_index(IX_SALE_INVOICE_TENANT_NUMBER, SALE_INVOICES, ["tenant_id", "invoice_number"], unique=True)
    except Exception:
        pass


def downgrade() -> None:
    bind = op.get_bind()

    # Best-effort: drop added sales columns/index; keep legacy data tables if risky.
    if _has_table(bind, SALES):
        try:
            if "ix_sales_sale_invoice_id" in _index_names(bind, SALES):
                op.drop_index("ix_sales_sale_invoice_id", table_name=SALES)
        except Exception:
            pass
        for col in [
            "line_profit", "line_total", "line_tax_amount", "line_subtotal",
            "gst_pct_snapshot", "unit_cost_snapshot", "unit_mrp_snapshot",
            "medicine_composition_snapshot", "medicine_name_snapshot", "sale_invoice_id",
        ]:
            try:
                if _has_column(bind, SALES, col):
                    if bind.dialect.name == "sqlite":
                        with op.batch_alter_table(SALES) as batch_op:
                            batch_op.drop_column(col)
                    else:
                        op.drop_column(SALES, col)
            except Exception:
                pass

    for table, idx in [
        (SALE_INVOICE_COUNTERS, "ix_sale_invoice_counters_tenant_id"),
        (SALE_INVOICES, IX_SALE_INVOICE_TENANT_NUMBER),
        (SALE_INVOICES, "ix_sale_invoices_customer_id"),
        (SALE_INVOICES, "ix_sale_invoices_tenant_id"),
    ]:
        try:
            if _has_table(bind, table) and idx in _index_names(bind, table):
                op.drop_index(idx, table_name=table)
        except Exception:
            pass

    for table in [SALE_INVOICE_COUNTERS, SALE_INVOICES]:
        try:
            if _has_table(bind, table):
                op.drop_table(table)
        except Exception:
            pass
