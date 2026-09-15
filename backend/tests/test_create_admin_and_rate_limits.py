"""
Tests for:
 - Task 1: create_admin script logic — user created with tenant_id cannot see another tenant's data.
 - Task 2: symptom-bot rate limiting — 429 after limit exceeded.
"""
import pytest
from app import models
from app.services.auth_service import hash_password, create_access_token


# ---------------------------------------------------------------------------
# Task 1 — create_admin tenant isolation
# ---------------------------------------------------------------------------

def _create_owner_via_script_logic(db, tenant):
    """
    Replicates exactly what scripts/create_admin.py does in its 'else' branch
    (creating a new owner). Used to verify the tenant_id is set correctly and
    that row-level security applies as expected.
    """
    import secrets
    password = secrets.token_urlsafe(16)
    user = models.User(
        tenant_id=tenant.id,          # required — must always be set
        username="script_admin",
        password_hash=hash_password(password),
        full_name="Script Admin",
        role="owner",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, password


def test_create_admin_user_has_tenant_id(db_session, tenant):
    """The created user must have tenant_id set — never None."""
    user, _ = _create_owner_via_script_logic(db_session, tenant)
    assert user.tenant_id is not None
    assert user.tenant_id == tenant.id


def test_create_admin_user_cannot_see_other_tenants_data(db_session, tenant, client):
    """
    Verifies the tenant isolation invariant:
    An owner created by the script for tenant A cannot query medicines
    belonging to tenant B. The global do_orm_execute filter in app/database.py
    is enforced at the SQLAlchemy level; this test hits it via the real HTTP
    client to prove the full stack is isolated.
    """
    # Create a second tenant with its own medicine
    tenant_b = models.Tenant(
        slug="pharmacy-b", shop_name="Pharmacy B",
        owner_name="Owner B", email="b@example.com"
    )
    db_session.add(tenant_b)
    db_session.commit()
    db_session.refresh(tenant_b)

    medicine_b = models.Medicine(
        tenant_id=tenant_b.id,
        particulars="TENANT B DRUG",
        normalized_name="TENANT B DRUG",
        unit="10S", mrp=50.0, current_stock=100,
    )
    db_session.add(medicine_b)
    db_session.commit()

    # Create owner for tenant A via the script logic
    user_a, _ = _create_owner_via_script_logic(db_session, tenant)
    assert user_a.tenant_id == tenant.id

    headers_a = {"Authorization": f"Bearer {create_access_token(user_a)}"}

    # Tenant A's owner hits the medicines list endpoint — must NOT see tenant B's drug
    resp = client.get("/medicines", headers=headers_a)
    assert resp.status_code == 200
    data = resp.json()
    # /medicines returns {"items": [...], "total": ..., "page": ..., "page_size": ...}
    items = data["items"] if isinstance(data, dict) else data
    names = [m["particulars"] for m in items]
    assert "TENANT B DRUG" not in names, (
        "Tenant A owner can see Tenant B medicine — cross-tenant isolation is broken!"
    )


# ---------------------------------------------------------------------------
# Task 2 — symptom-bot rate limiting
# ---------------------------------------------------------------------------

def test_symptom_bot_rate_limit(client, owner_headers):
    """
    After exceeding rate_limit_copilot (10/minute) the endpoint must return 429.
    We send 12 requests; at least the last one must be rate-limited.
    """
    status_codes = []
    for i in range(12):
        resp = client.post(
            "/symptom-bot/query",
            json={"message": f"headache {i}"},
            headers=owner_headers,
        )
        status_codes.append(resp.status_code)

    assert 429 in status_codes, (
        f"Expected a 429 after exceeding the symptom-bot rate limit, "
        f"got status codes: {status_codes}"
    )
