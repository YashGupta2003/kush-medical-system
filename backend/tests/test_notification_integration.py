"""
Integration tests for the Notification Engine.

Tests:
  1. Low-stock crossing during stock_service.record_sale produces a Notification row
     (end-to-end: sale → _add_ledger_entry → LowStockCrossedEvent → subscriber → Notification)
  2. Low-stock event does NOT fire when stock is already below threshold (only on crossing)
  3. WhatsApp delivery gracefully no-ops when Twilio isn't configured, without
     raising or preventing the in-app notification from being created
  4. GET /notifications endpoint returns notifications for the logged-in user
  5. PATCH /notifications/{id}/read marks as read
  6. GET /notifications/unread-count returns correct count
"""
import pytest
from decimal import Decimal
from app.services import stock_service, notification_service
from app.events.subscribers import register_all_subscribers
from app import models


def _register():
    """Re-register subscribers (conftest's app startup may not run in all test modes)."""
    register_all_subscribers()


# ---------------------------------------------------------------------------
# 1+2. Low-stock crossing during a real sale
# ---------------------------------------------------------------------------
def test_low_stock_crossing_creates_notification(db_session, tenant, sample_medicine, owner_user):
    """
    The key end-to-end integration test: a sale that crosses below threshold
    must produce a Notification row in the same transaction.
    """
    _register()

    # Set up: stock=15, threshold=10 — sale of 6 brings it to 9 (crosses below 10)
    sample_medicine.current_stock = 15
    sample_medicine.low_stock_threshold = 10
    db_session.commit()

    notifications_before = db_session.query(models.Notification).count()

    # This sale takes stock from 15 → 9, crossing the threshold
    stock_service.record_sale(db_session, tenant.id, sample_medicine.id, 6.0)

    notifications_after = db_session.query(models.Notification).count()
    assert notifications_after == notifications_before + 1, \
        "A Notification row should be created when stock crosses below threshold"

    notif = db_session.query(models.Notification).order_by(
        models.Notification.id.desc()
    ).first()
    assert notif.notification_type == "low_stock_crossed"
    assert str(sample_medicine.id) == notif.related_entity_id
    assert notif.related_entity_type == "medicine"
    assert notif.severity == "warning"
    assert notif.is_read is False


def test_low_stock_no_event_when_already_below_threshold(db_session, tenant, sample_medicine):
    """
    If stock is ALREADY below threshold before the sale (was crossed earlier),
    no second LowStockCrossedEvent should fire for further sales.
    This prevents notification spam on every subsequent sale while low.
    """
    _register()

    # Already below threshold
    sample_medicine.current_stock = 8
    sample_medicine.low_stock_threshold = 10
    db_session.commit()

    count_before = db_session.query(models.Notification).filter(
        models.Notification.notification_type == "low_stock_crossed"
    ).count()

    # Sale from 8 → 6 — still below threshold, no NEW crossing
    stock_service.record_sale(db_session, tenant.id, sample_medicine.id, 2.0)

    count_after = db_session.query(models.Notification).filter(
        models.Notification.notification_type == "low_stock_crossed"
    ).count()
    assert count_after == count_before, \
        "No new notification when stock was already below threshold (no crossing occurred)"


def test_no_low_stock_event_above_threshold(db_session, tenant, sample_medicine):
    """A sale that stays above threshold should not produce any notification."""
    _register()

    sample_medicine.current_stock = 20
    sample_medicine.low_stock_threshold = 10
    db_session.commit()

    count_before = db_session.query(models.Notification).filter(
        models.Notification.notification_type == "low_stock_crossed"
    ).count()

    # Sale from 20 → 15 — still above threshold
    stock_service.record_sale(db_session, tenant.id, sample_medicine.id, 5.0)

    count_after = db_session.query(models.Notification).filter(
        models.Notification.notification_type == "low_stock_crossed"
    ).count()
    assert count_after == count_before


# ---------------------------------------------------------------------------
# 3. WhatsApp no-op on unconfigured Twilio
# ---------------------------------------------------------------------------
def test_whatsapp_no_op_during_notification_creation(db_session, tenant, owner_user, monkeypatch):
    """
    Proven integration test: even with send_whatsapp=True, unconfigured Twilio
    must NOT raise or prevent the in-app notification from being written.
    """
    from app.config import settings
    monkeypatch.setattr(settings, "twilio_account_sid", "")
    monkeypatch.setattr(settings, "twilio_auth_token", "")

    # Should not raise even with send_whatsapp=True
    notif = notification_service.create_notification(
        db_session,
        notification_type="system",
        title="Test",
        body="WhatsApp should silently fail",
        recipient_user_id=owner_user.id,
        send_whatsapp=True,
    )
    db_session.commit()

    assert notif.id is not None
    fetched = db_session.query(models.Notification).get(notif.id)
    assert fetched is not None
    assert fetched.sent_at is None   # delivery wasn't completed


# ---------------------------------------------------------------------------
# 4–6. HTTP API integration
# ---------------------------------------------------------------------------
def test_notifications_api_list(client, owner_headers, owner_user, db_session, tenant):
    """GET /notifications returns the owner's notifications."""
    notification_service.create_notification(
        db_session, notification_type="system", title="API test",
        body="Test body", recipient_user_id=owner_user.id,
    )
    db_session.commit()

    res = client.get("/notifications", headers=owner_headers)
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["notification_type"] == "system"


def test_notifications_unread_count_api(client, owner_headers, owner_user, db_session, tenant):
    """GET /notifications/unread-count returns the right count."""
    for i in range(3):
        notification_service.create_notification(
            db_session, notification_type="system", title=f"N{i}",
            body="...", recipient_user_id=owner_user.id,
        )
    db_session.commit()

    res = client.get("/notifications/unread-count", headers=owner_headers)
    assert res.status_code == 200
    assert res.json()["count"] >= 3


def test_mark_notification_read_api(client, owner_headers, owner_user, db_session, tenant):
    """PATCH /notifications/{id}/read marks a notification as read."""
    notif = notification_service.create_notification(
        db_session, notification_type="system", title="Mark me",
        body="...", recipient_user_id=owner_user.id,
    )
    db_session.commit()

    res = client.patch(f"/notifications/{notif.id}/read", headers=owner_headers)
    assert res.status_code == 200
    assert res.json()["is_read"] is True


def test_notifications_require_auth(client):
    """Unauthenticated requests get 403 (HTTPBearer auto_error=False returns 403)."""
    res = client.get("/notifications")
    assert res.status_code in (401, 403)


def test_digest_send_now_owner_only(client, staff_headers):
    """POST /notifications/digest/send-now is owner-only."""
    res = client.post("/notifications/digest/send-now", headers=staff_headers)
    assert res.status_code == 403
