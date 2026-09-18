"""
Tests for Task 2: Pagination on customer search and ledger endpoints.

Verifies:
  - Response shape matches {items, total, page, page_size}
  - page_size is capped at 100 server-side
  - Pagination parameters work correctly (page/page_size)
"""
import pytest

from app import models
from app.services.auth_service import hash_password, create_access_token


def _make_customer(db, tenant, suffix=""):
    c = models.Customer(
        phone=f"+9198765{suffix}", name=f"Customer {suffix}", tenant_id=tenant.id
    )
    db.add(c)
    db.flush()
    return c


def test_search_customers_paginated_shape(client, db_session, tenant, owner_headers):
    """GET /customers returns {items, total, page, page_size}."""
    # Create 3 customers
    for i in range(3):
        _make_customer(db_session, tenant, str(i).zfill(5))
    db_session.commit()

    resp = client.get("/v1/customers?page=1&page_size=2", headers=owner_headers)
    assert resp.status_code == 200
    body = resp.json()

    assert "items" in body
    assert "total" in body
    assert "page" in body
    assert "page_size" in body

    assert body["page"] == 1
    assert body["page_size"] == 2
    assert body["total"] == 3
    assert len(body["items"]) == 2  # page 1 has 2 items


def test_search_customers_page2(client, db_session, tenant, owner_headers):
    """GET /customers?page=2 returns the remainder."""
    for i in range(3):
        _make_customer(db_session, tenant, str(10 + i).zfill(5))
    db_session.commit()

    resp = client.get("/v1/customers?page=2&page_size=2", headers=owner_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["page"] == 2
    assert len(body["items"]) == 1  # only 1 left on page 2


def test_search_customers_page_size_capped(client, db_session, tenant, owner_headers):
    """page_size > 100 is rejected (le=100 validator) or capped."""
    # With FastAPI's Query(le=100), a value of 200 should return 422
    resp = client.get("/v1/customers?page_size=200", headers=owner_headers)
    assert resp.status_code == 422  # validation error from Query(le=100)


def test_get_ledger_paginated_shape(client, db_session, tenant, owner_headers, owner_user):
    """GET /customers/{id}/ledger returns {items, total, page, page_size}."""
    customer = _make_customer(db_session, tenant, "99999")
    db_session.commit()

    # Add some credit entries
    from decimal import Decimal
    for i in range(3):
        entry = models.CustomerCredit(
            customer_id=customer.id,
            change_amount=Decimal("100"),
            resulting_balance=Decimal(str(100 * (i + 1))),
            reason="credit_sale",
        )
        db_session.add(entry)
    db_session.commit()

    resp = client.get(
        f"/v1/customers/{customer.id}/ledger?page=1&page_size=2",
        headers=owner_headers,
    )
    assert resp.status_code == 200
    body = resp.json()

    assert "items" in body
    assert "total" in body
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["page"] == 1
    assert body["page_size"] == 2


def test_get_ledger_page_size_capped(client, db_session, tenant, owner_headers):
    """Ledger endpoint rejects page_size > 100 with 422."""
    customer = _make_customer(db_session, tenant, "88888")
    db_session.commit()

    resp = client.get(
        f"/v1/customers/{customer.id}/ledger?page_size=200",
        headers=owner_headers,
    )
    assert resp.status_code == 422
