"""Backfill NULL tenant_id values left by the original single-shop schema.

Revision ID: 0025
Revises: 0024

Why this migration exists
-------------------------
Migration 0021 added nullable ``tenant_id`` columns to most tables, but did
not populate them. The runtime isolation guard hides NULL-tenant rows from
every shop, so any pre-0025 data would be silently invisible after the guard
is enabled. This migration repairs that data before the guard is deployed.

Strategy
--------
1. Single-tenant database (the overwhelmingly common case for this project):
   assign that one tenant to every NULL row in tenant-scoped tables. Curated
   graph reference edges (INTERACTS_WITH / TREATS) are intentionally global
   and are left NULL.
2. Multi-tenant database: derive tenant_id from a parent row where a reliable
   foreign-key path exists (bill -> bill item -> batch, user -> token, etc.).
   Rows that cannot be attributed remain NULL and must be reviewed manually;
   they are invisible rather than wrongly assigned to a tenant.

The operation is idempotent: it only touches rows where tenant_id IS NULL.
"""
from alembic import op
import sqlalchemy as sa

revision = '0025'
down_revision = '0024'
branch_labels = None
depends_on = None

# All tables whose ORM models carry tenant_id, except:
#   tenants                       (the tenant rows themselves)
#   cross_tenant_batch_alerts     (intentionally global)
#   regional_health_alerts        (intentionally global)
#   distributor_bill_templates    (tenant_id NOT NULL already)
#   distributor_field_accuracy    (tenant_id NOT NULL already)
TENANT_TABLES = (
    "medicines", "distributors", "bills", "bill_items", "rate_history",
    "user_mappings", "sales", "stock_ledger", "reorder_items",
    "medicine_batches", "users", "refresh_tokens", "medicine_salts",
    "graph_edges", "audit_ledger", "customers", "customer_credit_ledger",
    "pharmacy_nodes", "network_listings", "notifications",
    "surveillance_daily_counts", "cold_chain_units", "cold_chain_readings",
    "distributor_trust_scores", "prescriptions", "prescription_items",
)

GLOBAL_GRAPH_EDGE_TYPES = ("INTERACTS_WITH", "TREATS")

# table -> correlated scalar subquery that resolves the tenant from a parent.
PARENT_TENANT_SQL = {
    "bills": "SELECT tenant_id FROM distributors WHERE distributors.id = bills.distributor_id",
    "bill_items": "SELECT tenant_id FROM bills WHERE bills.id = bill_items.bill_id",
    "rate_history": "SELECT tenant_id FROM medicines WHERE medicines.id = rate_history.medicine_id",
    "user_mappings": "SELECT tenant_id FROM medicines WHERE medicines.id = user_mappings.medicine_id",
    "sales": "SELECT tenant_id FROM medicines WHERE medicines.id = sales.medicine_id",
    "stock_ledger": "SELECT tenant_id FROM medicines WHERE medicines.id = stock_ledger.medicine_id",
    "reorder_items": "SELECT tenant_id FROM medicines WHERE medicines.id = reorder_items.medicine_id",
    "medicine_batches": "SELECT tenant_id FROM medicines WHERE medicines.id = medicine_batches.medicine_id",
    "refresh_tokens": "SELECT tenant_id FROM users WHERE users.id = refresh_tokens.user_id",
    "medicine_salts": "SELECT tenant_id FROM medicines WHERE medicines.id = medicine_salts.medicine_id",
    "customer_credit_ledger": (
        "SELECT tenant_id FROM customers WHERE customers.id = customer_credit_ledger.customer_id"
    ),
    "network_listings": (
        "SELECT tenant_id FROM pharmacy_nodes "
        "WHERE pharmacy_nodes.id = network_listings.pharmacy_node_id"
    ),
    "notifications": (
        "SELECT tenant_id FROM users WHERE users.id = notifications.recipient_user_id"
    ),
    "cold_chain_readings": (
        "SELECT tenant_id FROM cold_chain_units WHERE cold_chain_units.id = cold_chain_readings.unit_id"
    ),
    "distributor_trust_scores": (
        "SELECT tenant_id FROM distributors WHERE distributors.id = distributor_trust_scores.distributor_id"
    ),
    "prescription_items": (
        "SELECT tenant_id FROM prescriptions WHERE prescriptions.id = prescription_items.prescription_id"
    ),
}


def _tables_present(conn):
    inspector = sa.inspect(conn)
    return set(inspector.get_table_names())


def _columns(conn, table):
    return {c["name"] for c in sa.inspect(conn).get_columns(table)}


def upgrade():
    conn = op.get_bind()
    existing = _tables_present(conn)
    if "tenants" not in existing:
        # Fresh database whose baseline has not created the schema yet —
        # nothing to backfill.
        return

    tenant_ids = [row[0] for row in conn.execute(sa.text("SELECT id FROM tenants"))]
    if not tenant_ids:
        return

    if len(tenant_ids) == 1:
        tenant_id = tenant_ids[0]
        for table in TENANT_TABLES:
            if table not in existing or "tenant_id" not in _columns(conn, table):
                continue
            if table == "graph_edges":
                conn.execute(
                    sa.text(
                        "UPDATE graph_edges SET tenant_id = :tid "
                        "WHERE tenant_id IS NULL AND edge_type NOT IN (:global_a, :global_b)"
                    ),
                    {
                        "tid": tenant_id,
                        "global_a": GLOBAL_GRAPH_EDGE_TYPES[0],
                        "global_b": GLOBAL_GRAPH_EDGE_TYPES[1],
                    },
                )
            else:
                conn.execute(
                    sa.text(f"UPDATE {table} SET tenant_id = :tid WHERE tenant_id IS NULL"),
                    {"tid": tenant_id},
                )
        return

    # Multi-tenant: only attribute rows where a parent proves ownership.
    for table, subquery in PARENT_TENANT_SQL.items():
        if table not in existing or "tenant_id" not in _columns(conn, table):
            continue
        conn.execute(sa.text(
            f"UPDATE {table} "
            f"SET tenant_id = ({subquery}) "
            f"WHERE tenant_id IS NULL AND ({subquery}) IS NOT NULL"
        ))

    # Curated graph reference data stays globally visible; tenant-derived
    # edges without a resolvable parent remain NULL and can be rebuilt with
    # graph_service.rebuild_full_graph() per tenant.


def downgrade():
    # Irreversible: the original tenant assignment is not recoverable from
    # the data itself. Intentionally a no-op.
    pass
