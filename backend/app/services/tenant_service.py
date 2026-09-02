"""
Tenant (Shop) management service.

Handles:
- Creating a new tenant (shop registration)
- Creating the initial owner User for a new tenant
- Generating URL-safe slugs from shop names
- Email verification token generation
"""
import hashlib
import re
import secrets
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app import models
from app.services.auth_service import hash_password


def _slugify(name: str) -> str:
    """Convert a shop name to a URL-safe slug, e.g. 'Kush Medical Hall' → 'kush-medical-hall'."""
    slug = name.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)    # remove non-alphanumeric except hyphen
    slug = re.sub(r'[\s_]+', '-', slug)      # spaces/underscores → hyphen
    slug = re.sub(r'-+', '-', slug)          # collapse multiple hyphens
    slug = slug.strip('-')
    return slug[:80]  # max 80 chars


def _make_unique_slug(db: Session, base_slug: str) -> str:
    """Ensure slug is unique by appending a counter if needed."""
    slug = base_slug
    counter = 1
    while db.query(models.Tenant).filter(models.Tenant.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug


def create_tenant_with_owner(
    db: Session,
    shop_name: str,
    owner_name: str,
    email: str,
    password: str,
    phone: str | None = None,
    gstin: str | None = None,
    city: str | None = None,
    address: str | None = None,
) -> tuple[models.Tenant, models.User, str]:
    """
    Register a new pharmacy:
    1. Check email uniqueness across all tenants
    2. Create Tenant row
    3. Create owner User linked to that tenant
    4. Generate email verification token
    Returns (tenant, user, verification_token) — caller sends the verification email.
    """
    # Check email not already taken (email is the global login identifier)
    existing = db.query(models.Tenant).filter(models.Tenant.email == email).first()
    if existing:
        raise HTTPException(400, f"An account with email '{email}' already exists. Please log in.")

    base_slug = _slugify(shop_name)
    if not base_slug:
        base_slug = "pharmacy"
    slug = _make_unique_slug(db, base_slug)

    verification_token = secrets.token_urlsafe(32)

    tenant = models.Tenant(
        slug=slug,
        shop_name=shop_name,
        owner_name=owner_name,
        email=email,
        phone=phone,
        gstin=gstin,
        city=city,
        address=address,
        plan="free",
        is_active=True,
        email_verified=False,
        email_verification_token=hashlib.sha256(verification_token.encode()).hexdigest(),
    )
    db.add(tenant)
    db.flush()  # get tenant.id without committing

    # Create the owner user. Username = email (unique within tenant scope)
    owner = models.User(
        tenant_id=tenant.id,
        username=email,
        password_hash=hash_password(password),
        full_name=owner_name,
        role="owner",
        is_active=True,
    )
    db.add(owner)
    db.commit()
    db.refresh(tenant)
    db.refresh(owner)

    return tenant, owner, verification_token


def verify_tenant_email(db: Session, token: str) -> models.Tenant:
    """
    Mark a tenant's email as verified using the raw verification token
    returned by create_tenant_with_owner.
    """
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    tenant = db.query(models.Tenant).filter(
        models.Tenant.email_verification_token == token_hash,
        models.Tenant.email_verified.is_(False),
    ).first()
    if not tenant:
        raise HTTPException(400, "Invalid or already-used verification link.")

    tenant.email_verified = True
    tenant.email_verification_token = None
    db.commit()
    db.refresh(tenant)
    return tenant


def get_tenant_by_id(db: Session, tenant_id: int) -> models.Tenant | None:
    return db.get(models.Tenant, tenant_id)
