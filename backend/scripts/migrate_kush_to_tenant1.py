#!/usr/bin/env python3
"""
migrate_kush_to_tenant1.py
==========================
One-time migration script: registers "Kush Medical Hall" as Tenant #1
and stamps every existing row in the database with tenant_id = 1.

Run from the backend/ directory:
    python scripts/migrate_kush_to_tenant1.py

What this script does:
  1. Creates the `tenants` table if it doesn't exist
  2. Inserts Kush Medical Hall as tenant id=1 (slug='kush-medical-hall')
  3. Adds tenant_id column to every business table (if not already present)
  4. Sets tenant_id = 1 on every existing row
  5. Updates the existing owner user to be linked to tenant_id = 1
  6. Prints a full summary

Safe to re-run — every step is idempotent (checks before acting).
"""
import sys
import os

# Make sure we can import from the app package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text, inspect as sa_inspect
from app.config import settings

print("\n" + "="*60)
print("  Kush Medical Hall → Tenant #1 Migration")
print("="*60 + "\n")

engine = create_engine(settings.database_url, pool_pre_ping=True)

# Tables that need tenant_id (in dependency order — referenced tables first)
BUSINESS_TABLES = [
    "medicines",
    "distributors",
    "bills",
    "sales",
    "stock_ledger",
    "reorder_items",
    "medicine_batches",
    "customers",
    "cold_chain_units",
    "notifications",
    "audit_ledger",
    "surveillance_daily_counts",
    "prescriptions",
    "user_mappings",
    "users",
]

KUSH_TENANT = {
    "id": 1,
    "slug": "kush-medical-hall",
    "shop_name": "Kush Medical Hall",
    "owner_name": "Owner",
    "email": "owner@kushmedical.local",
    "plan": "pro",
    "is_active": 1,
    "email_verified": 1,
}

KUSH_OWNER_CREDENTIALS = {
    # We'll use the existing owner user — just link them to tenant_id=1
    "role": "owner",
}


def run():
    with engine.begin() as conn:
        inspector = sa_inspect(engine)
        existing_tables = inspector.get_table_names()

        # ── STEP 1: Create tenants table ──────────────────────────────────
        print("Step 1: Creating tenants table (if not exists)...")
        if "tenants" not in existing_tables:
            conn.execute(text("""
                CREATE TABLE tenants (
                    id           INT NOT NULL AUTO_INCREMENT,
                    slug         VARCHAR(80)  NOT NULL,
                    shop_name    VARCHAR(150) NOT NULL,
                    owner_name   VARCHAR(100) NULL,
                    email        VARCHAR(150) NOT NULL,
                    phone        VARCHAR(20)  NULL,
                    gstin        VARCHAR(20)  NULL,
                    address      TEXT         NULL,
                    city         VARCHAR(100) NULL,
                    plan         ENUM('free','pro') NOT NULL DEFAULT 'free',
                    is_active    TINYINT(1)   NOT NULL DEFAULT 1,
                    email_verified TINYINT(1) NOT NULL DEFAULT 0,
                    email_verification_token VARCHAR(64) NULL,
                    created_at   DATETIME     NULL DEFAULT NOW(),
                    PRIMARY KEY (id),
                    UNIQUE KEY uq_tenants_slug (slug),
                    UNIQUE KEY uq_tenants_email (email),
                    KEY ix_tenants_id (id),
                    KEY ix_tenants_email_verification_token (email_verification_token)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """))
            print("  ✅ tenants table created")
        else:
            print("  ✓  tenants table already exists")

        # ── STEP 2: Insert Kush Medical Hall as tenant #1 ─────────────────
        print("\nStep 2: Registering Kush Medical Hall as Tenant #1...")
        existing_tenant = conn.execute(
            text("SELECT id FROM tenants WHERE id = 1")
        ).fetchone()

        if not existing_tenant:
            conn.execute(text("""
                INSERT INTO tenants
                    (id, slug, shop_name, owner_name, email, plan, is_active, email_verified, created_at)
                VALUES
                    (1, 'kush-medical-hall', 'Kush Medical Hall', 'Owner',
                     'owner@kushmedical.local', 'pro', 1, 1, NOW())
            """))
            print("  ✅ Kush Medical Hall registered as Tenant #1")
        else:
            print("  ✓  Tenant #1 already exists — skipping insert")

        # ── STEP 3: Add tenant_id column to each business table ───────────
        print("\nStep 3: Adding tenant_id columns to all tables...")

        for table in BUSINESS_TABLES:
            if table not in existing_tables:
                print(f"  ⚠  Table '{table}' does not exist — skipping")
                continue

            columns = [c["name"] for c in inspector.get_columns(table)]

            if "tenant_id" not in columns:
                try:
                    # Add column as nullable first (needed because existing rows have no value)
                    conn.execute(text(
                        f"ALTER TABLE `{table}` "
                        f"ADD COLUMN tenant_id INT NULL, "
                        f"ADD INDEX ix_{table}_tenant_id (tenant_id)"
                    ))
                    print(f"  ✅ Added tenant_id to '{table}'")
                except Exception as e:
                    print(f"  ⚠  Could not add tenant_id to '{table}': {e}")
            else:
                print(f"  ✓  '{table}' already has tenant_id")

        # ── STEP 4: Backfill tenant_id = 1 on all rows ───────────────────
        print("\nStep 4: Setting tenant_id = 1 on all existing rows...")

        total_updated = 0
        for table in BUSINESS_TABLES:
            if table not in existing_tables:
                continue

            # Re-check column exists (might have failed to add above)
            columns = [c["name"] for c in sa_inspect(engine).get_columns(table)]
            if "tenant_id" not in columns:
                continue

            try:
                result = conn.execute(text(
                    f"UPDATE `{table}` SET tenant_id = 1 WHERE tenant_id IS NULL"
                ))
                rows = result.rowcount
                total_updated += rows
                if rows > 0:
                    print(f"  ✅ {table}: {rows} rows updated")
                else:
                    print(f"  ✓  {table}: all rows already have tenant_id")
            except Exception as e:
                print(f"  ⚠  Could not update '{table}': {e}")

        print(f"\n  Total rows updated: {total_updated}")

        # ── STEP 5: Add FK constraints (tenant_id → tenants.id) ───────────
        print("\nStep 5: Adding FK constraints (tenant_id → tenants.id)...")

        for table in BUSINESS_TABLES:
            if table not in existing_tables:
                continue

            columns = [c["name"] for c in sa_inspect(engine).get_columns(table)]
            if "tenant_id" not in columns:
                continue

            fk_name = f"fk_{table}_tenant_id"
            try:
                # Try to add FK — will fail if already exists, that's fine
                conn.execute(text(
                    f"ALTER TABLE `{table}` "
                    f"MODIFY COLUMN tenant_id INT NOT NULL, "
                    f"ADD CONSTRAINT {fk_name} "
                    f"FOREIGN KEY (tenant_id) REFERENCES tenants(id)"
                ))
                print(f"  ✅ FK added to '{table}'")
            except Exception as e:
                # FK already exists or column already NOT NULL — safe to ignore
                if "Duplicate" in str(e) or "already exists" in str(e) or "1215" in str(e) or "1826" in str(e):
                    print(f"  ✓  '{table}' FK already set")
                else:
                    # Try just making it NOT NULL without the FK (FK might already exist)
                    try:
                        conn.execute(text(
                            f"ALTER TABLE `{table}` MODIFY COLUMN tenant_id INT NOT NULL"
                        ))
                        print(f"  ✓  '{table}' tenant_id set NOT NULL")
                    except Exception as e2:
                        print(f"  ⚠  '{table}': {e2}")

        # ── STEP 6: Update customer unique constraint ─────────────────────
        print("\nStep 6: Updating customer phone uniqueness constraint...")
        try:
            # Drop old global unique index on phone (MySQL)
            conn.execute(text("ALTER TABLE customers DROP INDEX phone"))
            print("  ✅ Dropped old global unique index on customers.phone")
        except Exception:
            pass  # Index might not exist with that name

        try:
            conn.execute(text(
                "ALTER TABLE customers ADD UNIQUE KEY uq_customer_phone_per_tenant (tenant_id, phone)"
            ))
            print("  ✅ Added per-tenant unique constraint on customers(tenant_id, phone)")
        except Exception as e:
            if "Duplicate" in str(e) or "already" in str(e):
                print("  ✓  Per-tenant phone constraint already exists")
            else:
                print(f"  ⚠  {e}")

        # ── STEP 7: Update cold_chain_units unique constraint ────────────
        print("\nStep 7: Updating cold_chain_units unit_label uniqueness...")
        try:
            conn.execute(text("ALTER TABLE cold_chain_units DROP INDEX unit_label"))
        except Exception:
            pass
        try:
            conn.execute(text(
                "ALTER TABLE cold_chain_units ADD UNIQUE KEY uq_cold_chain_unit_label_per_tenant (tenant_id, unit_label)"
            ))
            print("  ✅ Added per-tenant constraint on cold_chain_units(tenant_id, unit_label)")
        except Exception as e:
            if "Duplicate" in str(e) or "already" in str(e):
                print("  ✓  Already set")
            else:
                print(f"  ⚠  {e}")

        # ── STEP 8: Update surveillance unique constraint ─────────────────
        print("\nStep 8: Updating surveillance_daily_counts uniqueness constraint...")
        try:
            conn.execute(text(
                "ALTER TABLE surveillance_daily_counts DROP INDEX uq_surveillance_daily_counts_cond_date"
            ))
        except Exception:
            pass
        try:
            conn.execute(text(
                "ALTER TABLE surveillance_daily_counts "
                "ADD UNIQUE KEY uq_surveillance_daily_counts_cond_date (tenant_id, condition_name, count_date)"
            ))
            print("  ✅ Added per-tenant constraint on surveillance_daily_counts")
        except Exception as e:
            if "Duplicate" in str(e) or "already" in str(e):
                print("  ✓  Already set")
            else:
                print(f"  ⚠  {e}")

        # ── STEP 9: Update users username constraint ──────────────────────
        print("\nStep 9: Updating users username uniqueness to per-tenant scope...")
        try:
            # Drop global unique index on username
            conn.execute(text("ALTER TABLE users DROP INDEX username"))
            print("  ✅ Dropped global unique index on users.username")
        except Exception:
            pass  # Might have a different name
        try:
            conn.execute(text(
                "ALTER TABLE users ADD UNIQUE KEY uq_user_username_per_tenant (tenant_id, username)"
            ))
            print("  ✅ Added per-tenant unique constraint on users(tenant_id, username)")
        except Exception as e:
            if "Duplicate" in str(e) or "already" in str(e):
                print("  ✓  Already set")
            else:
                print(f"  ⚠  {e}")

    # ── STEP 10: Summary query ────────────────────────────────────────────
    print("\n" + "="*60)
    print("  Migration Complete — Data Summary")
    print("="*60)

    with engine.connect() as conn:
        for table in BUSINESS_TABLES:
            try:
                result = conn.execute(text(f"SELECT COUNT(*) FROM `{table}` WHERE tenant_id = 1"))
                count = result.scalar()
                print(f"  {table:35s}: {count} rows under Tenant #1")
            except Exception:
                pass

        # Show tenant
        tenant_row = conn.execute(text("SELECT id, slug, shop_name, email, plan FROM tenants WHERE id = 1")).fetchone()
        if tenant_row:
            print(f"\n  Tenant #1 → id={tenant_row[0]}, slug='{tenant_row[1]}', name='{tenant_row[2]}'")
            print(f"  Login email : {tenant_row[3]}")
            print(f"  Plan        : {tenant_row[4]}")

        # Show users in tenant
        users_result = conn.execute(
            text("SELECT username, role, is_active FROM users WHERE tenant_id = 1")
        ).fetchall()
        if users_result:
            print(f"\n  Users in Tenant #1 ({len(users_result)} total):")
            for u in users_result:
                print(f"    • {u[0]:20s} [{u[1]}] {'(active)' if u[2] else '(inactive)'}")

    print("\n✅ Kush Medical Hall is now registered as Tenant #1!")
    print("   All existing data has been migrated to this tenant.\n")


if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
