"""
Unit tests for notification_service.py

Tests:
  1. create_notification — creates a row, returns the model
  2. has_recent_notification — deduplication check
  3. get_notifications_for_user — owner gets broadcast + own; staff gets only own
  4. get_unread_count — correct count before/after mark_read
  5. mark_read — marks as read, respects ownership
  6. mark_all_read — marks all unread as read
  7. build_daily_digest — returns structured dict with all expected keys
  8. WhatsApp graceful no-op — send_whatsapp=True without Twilio configured
     doesn't raise, still creates the in-app notification
"""
import pytest
from app.services import notification_service
from app import models


# ---------------------------------------------------------------------------
# Basic create
# ---------------------------------------------------------------------------
def test_create_notification_creates_row(db_session, owner_user):
    notif = notification_service.create_notification(
        db_session,
        notification_type="low_stock_crossed",
        title="Low Stock: TestMed",
        body="Stock dropped below threshold",
        severity="warning",
        recipient_user_id=owner_user.id,
        related_entity_type="medicine",
        related_entity_id="42",
    )
    db_session.commit()

    assert notif.id is not None
    assert notif.notification_type == "low_stock_crossed"
    assert notif.is_read is False
    assert notif.recipient_user_id == owner_user.id
    assert notif.related_entity_id == "42"


def test_create_notification_broadcast_null_recipient(db_session):
    """recipient_user_id=None means broadcast to all owners."""
    notif = notification_service.create_notification(
        db_session,
        notification_type="anomaly_flagged",
        title="Anomaly detected",
        body="Unusual price jump",
        recipient_user_id=None,
    )
    db_session.commit()
    assert notif.recipient_user_id is None


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------
def test_has_recent_notification_true(db_session):
    """Returns True when a matching notification exists within the window."""
    notification_service.create_notification(
        db_session,
        notification_type="adherence_overdue",
        title="T",
        body="B",
        related_entity_type="customer:1:medicine",
        related_entity_id="5",
    )
    db_session.commit()

    result = notification_service.has_recent_notification(
        db_session,
        notification_type="adherence_overdue",
        related_entity_type="customer:1:medicine",
        related_entity_id="5",
        within_hours=168,
    )
    assert result is True


def test_has_recent_notification_false_different_entity(db_session):
    """Returns False when entity_id differs — different patient/medicine pair."""
    notification_service.create_notification(
        db_session,
        notification_type="adherence_overdue",
        title="T",
        body="B",
        related_entity_type="customer:1:medicine",
        related_entity_id="5",
    )
    db_session.commit()

    result = notification_service.has_recent_notification(
        db_session,
        notification_type="adherence_overdue",
        related_entity_type="customer:1:medicine",
        related_entity_id="99",   # different medicine
        within_hours=168,
    )
    assert result is False


# ---------------------------------------------------------------------------
# Get notifications for user
# ---------------------------------------------------------------------------
def test_owner_sees_broadcast_and_own(db_session, owner_user, staff_user):
    # Broadcast notification (no recipient)
    notification_service.create_notification(
        db_session, notification_type="daily_digest", title="Digest",
        body="...", recipient_user_id=None,
    )
    # Owner's own notification
    notification_service.create_notification(
        db_session, notification_type="low_stock_crossed", title="Low",
        body="...", recipient_user_id=owner_user.id,
    )
    # Staff's own notification — should NOT appear in owner's list
    notification_service.create_notification(
        db_session, notification_type="system", title="Staff",
        body="...", recipient_user_id=staff_user.id,
    )
    db_session.commit()

    owner_notifs = notification_service.get_notifications_for_user(db_session, owner_user)
    # Owner should see broadcast + their own, but NOT staff's
    assert len(owner_notifs) == 2
    for n in owner_notifs:
        assert n.recipient_user_id in (None, owner_user.id)


def test_staff_sees_only_own(db_session, owner_user, staff_user):
    notification_service.create_notification(
        db_session, notification_type="daily_digest", title="Digest",
        body="...", recipient_user_id=None,   # broadcast — staff should NOT see
    )
    notification_service.create_notification(
        db_session, notification_type="system", title="Staff note",
        body="...", recipient_user_id=staff_user.id,
    )
    db_session.commit()

    staff_notifs = notification_service.get_notifications_for_user(db_session, staff_user)
    assert len(staff_notifs) == 1
    assert staff_notifs[0].recipient_user_id == staff_user.id


# ---------------------------------------------------------------------------
# Unread count
# ---------------------------------------------------------------------------
def test_unread_count_decreases_after_mark_read(db_session, owner_user):
    n1 = notification_service.create_notification(
        db_session, notification_type="system", title="A", body="A",
        recipient_user_id=owner_user.id,
    )
    notification_service.create_notification(
        db_session, notification_type="system", title="B", body="B",
        recipient_user_id=owner_user.id,
    )
    db_session.commit()

    assert notification_service.get_unread_count(db_session, owner_user) == 2

    notification_service.mark_read(db_session, n1.id, owner_user)
    assert notification_service.get_unread_count(db_session, owner_user) == 1


# ---------------------------------------------------------------------------
# Mark read — ownership enforcement
# ---------------------------------------------------------------------------
def test_mark_read_rejects_other_users_notification(db_session, owner_user, staff_user):
    notif = notification_service.create_notification(
        db_session, notification_type="system", title="Owner only",
        body="...", recipient_user_id=owner_user.id,
    )
    db_session.commit()

    # Staff tries to mark owner's notification — should return None (no-op)
    result = notification_service.mark_read(db_session, notif.id, staff_user)
    assert result is None

    # Original notification is still unread
    db_session.refresh(notif)
    assert notif.is_read is False


def test_mark_all_read_count(db_session, owner_user):
    for _ in range(3):
        notification_service.create_notification(
            db_session, notification_type="system", title="X", body="X",
            recipient_user_id=owner_user.id,
        )
    db_session.commit()

    count = notification_service.mark_all_read(db_session, owner_user)
    assert count == 3
    assert notification_service.get_unread_count(db_session, owner_user) == 0


# ---------------------------------------------------------------------------
# Build daily digest
# ---------------------------------------------------------------------------
def test_build_daily_digest_returns_expected_keys(db_session, owner_user):
    digest = notification_service.build_daily_digest(db_session, owner_user.id)
    expected_keys = {
        "generated_at", "user_id", "adherence_overdue_count",
        "adherence_alerts_sample", "outstanding_credit_total",
        "outstanding_credit_customers", "near_expiry_critical_count",
        "low_stock_count", "anomaly_flag_count",
    }
    assert expected_keys.issubset(digest.keys())
    assert digest["user_id"] == owner_user.id


# ---------------------------------------------------------------------------
# WhatsApp graceful no-op
# ---------------------------------------------------------------------------
def test_whatsapp_no_op_when_twilio_not_configured(db_session, owner_user, monkeypatch):
    """
    send_whatsapp=True with no Twilio credentials configured should:
      - Still create the in_app notification row (priority: never lose the alert)
      - NOT raise any exception
      - sent_at should remain None (delivery wasn't attempted successfully)
    """
    # Ensure settings look unconfigured
    from app.config import settings
    monkeypatch.setattr(settings, "twilio_account_sid", "")
    monkeypatch.setattr(settings, "twilio_auth_token", "")
    monkeypatch.setattr(settings, "twilio_whatsapp_number", "")

    notif = notification_service.create_notification(
        db_session,
        notification_type="daily_digest",
        title="Test digest",
        body="...",
        recipient_user_id=owner_user.id,
        send_whatsapp=True,   # Requested, but Twilio not configured
    )
    db_session.commit()

    assert notif.id is not None   # in-app record always created
    assert notif.is_read is False
    assert notif.sent_at is None   # no delivery happened
