"""
Regression tests for the GLOBAL multi-tenant isolation layer.

These tests deliberately install the same `do_orm_execute` / `before_flush`
listeners used in production (see tests/conftest.py). Before this suite was
added, the tests used a bare sessionmaker, so every test passed with tenant
isolation completely disabled — including bulk writes and NULL-tenant inserts.

Covered here:
  1. SELECT scoping (including Session.get and relationship loads)
  2. bulk ORM UPDATE / DELETE scoping
  3. reassignment of an existing row to another tenant is refused
  4. tenant propagation on INSERT from session.info["tenant_id"]
  5. NULL-tenant rows remain invisible
  6. explicit, auditable bypass for genuine global operations
  7. cross-tenant notification broadcasts and mark_all_read
  8. tenant-scoped vs globally-curated graph edges
  9. refresh tokens inherit their user's tenant
"""
import pytest
from sqlalchemy import select

from app import models
from app.database import (
    TenantIsolationError,
    bypass_tenant_filter,
    tenant_context,
)
from app.services import (
    audit_service,
    auth_service,
    graph_service,
    notification_service,
)
from app.services.auth_service import hash_password


def _make_tenant(db, *, slug, shop_name, email):
    tenant = models.Tenant(
        slug=slug, shop_name=shop_name, owner_name="Owner",
        email=email, is_active=True,
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


def _make_medicine(db, tenant_id, name):
    med = models.Medicine(
        tenant_id=tenant_id, particulars=name, normalized_name=name.upper(),
        current_stock=10,
    )
    db.add(med)
    db.commit()
    db.refresh(med)
    return med


@pytest.fixture()
def two_tenants(db_session):
    first = _make_tenant(
        db_session, slug="tenant-one", shop_name="One Pharmacy",
        email="one@example.com",
    )
    second = _make_tenant(
        db_session, slug="tenant-two", shop_name="Two Pharmacy",
        email="two@example.com",
    )
    return first, second


# ---------------------------------------------------------------------------
# 1. SELECT scoping
# ---------------------------------------------------------------------------
def test_select_and_get_are_tenant_scoped(db_session, two_tenants):
    first, second = two_tenants
    mine = _make_medicine(db_session, first.id, "MINE")
    theirs = _make_medicine(db_session, second.id, "THEIRS")

    with tenant_context(db_session, first.id):
        ids = {m.id for m in db_session.scalars(select(models.Medicine)).all()}
        assert ids == {mine.id}
        assert db_session.get(models.Medicine, theirs.id) is None

    with tenant_context(db_session, second.id):
        ids = {m.id for m in db_session.scalars(select(models.Medicine)).all()}
        assert ids == {theirs.id}


def test_relationship_load_is_tenant_scoped(db_session, two_tenants):
    """with_loader_criteria must also apply to relationship/joined loads."""
    from sqlalchemy.orm import joinedload

    first, second = two_tenants
    mine = _make_medicine(db_session, first.id, "MINE")
    theirs = _make_medicine(db_session, second.id, "THEIRS")
    for medicine in (mine, theirs):
        db_session.add(models.Bill(
            tenant_id=medicine.tenant_id, invoice_no=f"INV-{medicine.id}",
            status="pending_review",
        ))
        db_session.flush()
    db_session.commit()

    with tenant_context(db_session, first.id):
        bills = db_session.scalars(
            select(models.Bill).options(joinedload(models.Bill.items))
        ).unique().all()
        assert len(bills) == 1
        assert bills[0].invoice_no == f"INV-{mine.id}"


# ---------------------------------------------------------------------------
# 2. Bulk UPDATE / DELETE scoping
# ---------------------------------------------------------------------------
def test_bulk_update_does_not_touch_other_tenants(db_session, two_tenants):
    first, second = two_tenants
    mine = _make_medicine(db_session, first.id, "MINE")
    theirs = _make_medicine(db_session, second.id, "THEIRS")

    with tenant_context(db_session, first.id):
        db_session.query(models.Medicine).update(
            {models.Medicine.particulars: "CHANGED"}, synchronize_session=False
        )
        db_session.commit()

    db_session.expire_all()
    assert db_session.get(models.Medicine, mine.id).particulars == "CHANGED"
    assert db_session.get(models.Medicine, theirs.id).particulars == "THEIRS"


def test_bulk_delete_does_not_touch_other_tenants(db_session, two_tenants):
    first, second = two_tenants
    mine = _make_medicine(db_session, first.id, "MINE")
    theirs = _make_medicine(db_session, second.id, "THEIRS")
    mine_id, theirs_id = mine.id, theirs.id

    with tenant_context(db_session, first.id):
        db_session.query(models.Medicine).delete(synchronize_session=False)
        db_session.commit()

    # synchronize_session=False leaves stale objects in the identity map;
    # a fresh session (as every HTTP request gets) would not have them.
    db_session.expunge_all()
    assert db_session.get(models.Medicine, mine_id) is None
    assert db_session.get(models.Medicine, theirs_id) is not None


# ---------------------------------------------------------------------------
# 3. Existing rows cannot silently move tenants
# ---------------------------------------------------------------------------
def test_cross_tenant_reassignment_is_refused(db_session, two_tenants):
    first, second = two_tenants
    mine = _make_medicine(db_session, first.id, "MINE")

    with tenant_context(db_session, first.id):
        mine = db_session.get(models.Medicine, mine.id)
        mine.tenant_id = second.id
        with pytest.raises(TenantIsolationError):
            db_session.flush()
        db_session.rollback()


# ---------------------------------------------------------------------------
# 4/5. INSERT propagation and NULL-tenant invisibility
# ---------------------------------------------------------------------------
def test_insert_inherits_active_tenant(db_session, two_tenants):
    first, _second = two_tenants
    with tenant_context(db_session, first.id):
        med = models.Medicine(
            particulars="NEW", normalized_name="NEW", current_stock=1,
        )
        db_session.add(med)
        db_session.flush()
        assert med.tenant_id == first.id
        db_session.commit()

    with tenant_context(db_session, first.id):
        assert db_session.get(models.Medicine, med.id) is not None


def test_null_tenant_row_is_invisible_to_every_tenant(db_session, two_tenants):
    first, second = two_tenants
    orphan = _make_medicine(db_session, None, "ORPHAN")

    for tenant in (first, second):
        with tenant_context(db_session, tenant.id):
            assert db_session.get(models.Medicine, orphan.id) is None


def test_tenant_context_restores_previous_context(db_session, two_tenants):
    first, second = two_tenants
    with tenant_context(db_session, first.id):
        with tenant_context(db_session, second.id):
            assert db_session.info["tenant_id"] == second.id
        assert db_session.info["tenant_id"] == first.id
    assert "tenant_id" not in db_session.info


# ---------------------------------------------------------------------------
# 6. Explicit global bypass
# ---------------------------------------------------------------------------
def test_bypass_tenant_filter_restores_state(db_session, two_tenants):
    first, _second = two_tenants
    _make_medicine(db_session, first.id, "MINE")
    _make_medicine(db_session, None, "ORPHAN")

    with tenant_context(db_session, first.id):
        assert db_session.query(models.Medicine).count() == 1
        with bypass_tenant_filter(db_session):
            assert db_session.info["skip_tenant_filter"] is True
            assert db_session.query(models.Medicine).count() == 2
        assert "skip_tenant_filter" not in db_session.info
        assert db_session.query(models.Medicine).count() == 1


def test_bypass_does_not_leave_other_tenant_rows_in_identity_map(
    db_session, two_tenants
):
    first, second = two_tenants
    mine = _make_medicine(db_session, first.id, "MINE")
    theirs = _make_medicine(db_session, second.id, "THEIRS")

    with tenant_context(db_session, first.id):
        with bypass_tenant_filter(db_session):
            foreign = db_session.get(models.Medicine, theirs.id)
            assert foreign is not None
        # Session.get() checks the identity map before emitting SQL; without
        # eviction on bypass exit this would leak the other shop's row.
        assert db_session.get(models.Medicine, theirs.id) is None
        assert db_session.get(models.Medicine, mine.id) is not None


# ---------------------------------------------------------------------------
# 7. Notifications — the original silent data-loss bug
# ---------------------------------------------------------------------------
def test_broadcast_notifications_are_tenant_scoped(db_session, two_tenants):
    first, second = two_tenants

    def owner_for(tenant, username):
        user = models.User(
            tenant_id=tenant.id, username=username,
            password_hash=hash_password("pass"), role="owner", is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    owner_one = owner_for(first, "owner-one")
    owner_two = owner_for(second, "owner-two")

    broadcast = notification_service.create_notification(
        db_session, notification_type="daily_digest", title="Digest",
        body="...", recipient_user_id=None, tenant_id=first.id,
    )
    db_session.commit()

    assert notification_service.get_notifications_for_user(db_session, owner_one) == [broadcast]
    assert notification_service.get_notifications_for_user(db_session, owner_two) == []

    # The dangerous case: bulk UPDATE with IS NULL recipient used to mark
    # EVERY tenant's broadcasts as read.
    assert notification_service.mark_all_read(db_session, owner_two) == 0
    assert notification_service.mark_all_read(db_session, owner_one) == 1
    db_session.refresh(broadcast)
    assert broadcast.is_read is True


def test_notification_creation_infers_tenant_from_recipient(db_session, two_tenants):
    first, second = two_tenants
    owner = models.User(
        tenant_id=second.id, username="owner-two",
        password_hash=hash_password("pass"), role="owner", is_active=True,
    )
    db_session.add(owner)
    db_session.commit()
    db_session.refresh(owner)

    notif = notification_service.create_notification(
        db_session, notification_type="low_stock_crossed", title="Low",
        body="...", recipient_user_id=owner.id,
    )
    db_session.commit()
    assert notif.tenant_id == second.id


# ---------------------------------------------------------------------------
# 8. Graph edges — tenant-derived vs curated global reference data
# ---------------------------------------------------------------------------
def test_graph_edges_scope_tenant_rows_but_allow_curated_globals(db_session, two_tenants):
    first, second = two_tenants
    derived = graph_service.add_edge(
        db_session, "medicine", 1, "CONTAINS", "salt", "PARACETAMOL",
        tenant_id=first.id, replace=False,
    )
    curated = graph_service.add_edge(
        db_session, "salt", "PARACETAMOL", "INTERACTS_WITH", "salt", "IBUPROFEN",
        tenant_id=None, replace=False,
    )
    db_session.commit()

    with tenant_context(db_session, first.id):
        visible = {e.id for e in db_session.query(models.GraphEdge).all()}
        assert derived.id in visible
        assert curated.id in visible
    with tenant_context(db_session, second.id):
        visible = {e.id for e in db_session.query(models.GraphEdge).all()}
        assert derived.id not in visible
        assert curated.id in visible


def test_add_edge_uses_active_tenant_when_not_provided(db_session, two_tenants):
    first, _second = two_tenants
    with tenant_context(db_session, first.id):
        edge = graph_service.add_edge(
            db_session, "medicine", 1, "CONTAINS", "salt", "PARACETAMOL",
            tenant_id=None, replace=False,
        )
        db_session.flush()
        assert edge.tenant_id == first.id


# ---------------------------------------------------------------------------
# 9. Refresh tokens
# ---------------------------------------------------------------------------
def test_refresh_token_inherits_user_tenant(db_session, two_tenants):
    first, _second = two_tenants
    user = models.User(
        tenant_id=first.id, username="token-user",
        password_hash=hash_password("pass"), role="owner", is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    raw = auth_service.create_refresh_token(db_session, user)
    token = db_session.query(models.RefreshToken).filter_by(
        token_hash=auth_service._hash_token(raw)
    ).one()
    assert token.tenant_id == first.id


def test_revoke_all_tokens_requires_matching_tenant(db_session, two_tenants):
    first, second = two_tenants

    def make_user(tenant, username):
        user = models.User(
            tenant_id=tenant.id, username=username,
            password_hash=hash_password("pass"), role="owner", is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    user_one = make_user(first, "token-one")
    user_two = make_user(second, "token-two")
    auth_service.create_refresh_token(db_session, user_one)
    auth_service.create_refresh_token(db_session, user_two)
    db_session.commit()

    # Wrong tenant must not touch user_one's tokens.
    assert auth_service.revoke_all_tokens_for_user(
        db_session, user_one.id, tenant_id=second.id
    ) == 0
    token_one = db_session.query(models.RefreshToken).filter_by(
        user_id=user_one.id
    ).one()
    assert token_one.revoked is False

    assert auth_service.revoke_all_tokens_for_user(
        db_session, user_one.id, tenant_id=first.id
    ) == 1
    db_session.expire_all()
    assert db_session.get(models.RefreshToken, token_one.id).revoked is True
    token_two = db_session.query(models.RefreshToken).filter_by(
        user_id=user_two.id
    ).one()
    assert token_two.revoked is False


def test_curated_graph_edge_stays_global_under_tenant_context(db_session, two_tenants):
    first, second = two_tenants
    with tenant_context(db_session, first.id):
        edge = graph_service.add_edge(
            db_session, "salt", "PARACETAMOL", "TREATS", "condition", "FEVER",
            tenant_id=None, replace=False,
        )
        db_session.flush()
        assert edge.tenant_id is None
        edge_id = edge.id
    db_session.commit()

    # The whole point of a curated edge: both shops can read it.
    for tenant in (first, second):
        with tenant_context(db_session, tenant.id):
            assert db_session.get(models.GraphEdge, edge_id) is not None


def test_audit_hash_chain_is_global_but_ledger_view_is_tenant_scoped(
    db_session, two_tenants
):
    first, second = two_tenants
    first_entry = audit_service.log_event(
        db_session, "tenant_one_event", 1,
        {"tenant_id": first.id, "note": "one"},
    )
    second_entry = audit_service.log_event(
        db_session, "tenant_two_event", 2,
        {"tenant_id": second.id, "note": "two"},
    )
    db_session.commit()

    # The second entry must link to the first, even across tenant boundaries.
    assert second_entry.previous_hash == first_entry.entry_hash

    with tenant_context(db_session, first.id):
        report = audit_service.verify_chain(db_session)
        entries, total = audit_service.get_ledger_paginated(db_session)

    assert report["total_entries"] == 2
    assert report["is_valid"] is True
    assert total == 1  # browsing the ledger is correctly shop-scoped
    assert {e.event_type for e in entries} == {"tenant_one_event"}
