"""
Create or reset an owner account for an existing tenant.

Usage:
    venv/bin/python scripts/create_admin.py --tenant-id 1
    venv/bin/python scripts/create_admin.py --tenant-slug my-pharmacy
    venv/bin/python scripts/create_admin.py --tenant-id 1 --force   # reset password of existing owner

Every user, including owner accounts, MUST belong to a specific tenant.
A user without a tenant_id would bypass the global row-level security filter
in app/database.py and could read/write every tenant's data — that is a
cross-tenant data breach. This script enforces a valid tenant on all paths.
"""
import argparse
import sys
import secrets

from app.database import SessionLocal, Base, engine
from app import models
from app.services.auth_service import hash_password


def main():
    parser = argparse.ArgumentParser(
        description="Create or reset an owner account for an existing tenant."
    )
    tenant_group = parser.add_mutually_exclusive_group(required=True)
    tenant_group.add_argument(
        "--tenant-id",
        type=int,
        metavar="ID",
        help="Database ID of the tenant to create/reset the owner for.",
    )
    tenant_group.add_argument(
        "--tenant-slug",
        metavar="SLUG",
        help="URL slug of the tenant to create/reset the owner for.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force overwrite of an existing owner's password.",
    )
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # ── Resolve tenant ────────────────────────────────────────────────────────
    if args.tenant_id is not None:
        tenant = db.query(models.Tenant).filter(models.Tenant.id == args.tenant_id).first()
        identifier = f"id={args.tenant_id}"
    else:
        tenant = db.query(models.Tenant).filter(models.Tenant.slug == args.tenant_slug).first()
        identifier = f"slug='{args.tenant_slug}'"

    if not tenant:
        print(f"ERROR: No tenant found with {identifier}. Create the tenant first.")
        sys.exit(1)

    print(f"Tenant found: [{tenant.id}] {tenant.shop_name} (slug={tenant.slug})")

    # ── Find existing owner for this specific tenant ──────────────────────────
    existing_owner = (
        db.query(models.User)
        .filter(models.User.role == "owner", models.User.tenant_id == tenant.id)
        .first()
    )

    password = secrets.token_urlsafe(16)

    if existing_owner:
        if not args.force:
            print(
                f"Owner already exists for this tenant: '{existing_owner.username}'. "
                "Use --force to overwrite their password."
            )
            sys.exit(1)

        existing_owner.password_hash = hash_password(password)
        db.commit()
        print(f"Password reset for owner '{existing_owner.username}' (tenant: {tenant.shop_name}).")
    else:
        user = models.User(
            tenant_id=tenant.id,          # REQUIRED — prevents cross-tenant god-mode
            username="admin",
            password_hash=hash_password(password),
            full_name="Admin User",
            role="owner",
            is_active=True,
        )
        db.add(user)
        db.commit()
        print(f"Owner 'admin' created for tenant '{tenant.shop_name}' (id={tenant.id}).")

    print(f"\nNEW PASSWORD (save this, it will not be shown again): {password}\n")


if __name__ == "__main__":
    main()
