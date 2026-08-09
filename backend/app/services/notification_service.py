"""
Notification Engine — the proactive alerting layer that ties every Pillar
together into something an owner actually sees without opening six tabs.

Design philosophy (why this module exists):
  All six Pillars already generate high-value signals — adherence alerts,
  anomaly flags, low-stock crossings, outstanding credit, near-expiry,
  TrustChain tamper detection — but every single one of them was passive:
  the data sat in a dashboard tab until someone opened it. A real pharmacy
  owner is doing consultations, managing suppliers, and running the counter
  all day. They WILL miss things unless the system proactively surfaces them.

  This module is the single write path for all notifications, exactly
  mirroring audit_service.log_event's "one writer, everyone else calls it"
  convention. No other module should INSERT into the notifications table
  directly.

Delivery design decision:
  Channel "in_app" is always written regardless of external delivery (WhatsApp
  etc.) — so the notification center always has a complete record even if
  Twilio isn't configured. External delivery is a best-effort add-on, not the
  source of truth. This means the notification table is the canonical record,
  and `sent_at` being set means "was attempted for external delivery" rather
  than "was definitively delivered."

Deduplication strategy for adherence alerts:
  The Celery task calls this module's `has_recent_notification()` helper before
  creating a new alert — checking whether a notification of the same type for
  the same (customer_id, medicine_id) pair exists within the last 7 days. This
  is implemented via the `related_entity_type`/`related_entity_id` columns, which
  for adherence alerts encode "customer:{customer_id}:medicine:{medicine_id}" —
  no separate dedup table needed.
"""
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import desc, and_

from app import models
from app.core.logging import get_logger

logger = get_logger("notification_service")

# How long before an adherence/low-stock alert can fire again for the same entity.
NOTIFICATION_DEDUP_HOURS = 7 * 24   # 7 days


def create_notification(
    db: Session,
    *,
    notification_type: str,
    title: str,
    body: str,
    severity: str = "info",
    recipient_user_id: Optional[int] = None,
    related_entity_type: Optional[str] = None,
    related_entity_id: Optional[str] = None,
    channel: str = "in_app",
    send_whatsapp: bool = False,
) -> models.Notification:
    """
    Single write path for all notifications.

    recipient_user_id=None means "all owner accounts" — the frontend's
    unread-count query handles this by filtering for (recipient_user_id=user.id
    OR recipient_user_id IS NULL) combined with role='owner'.

    If send_whatsapp=True, attempts WhatsApp delivery via whatsapp_service.
    On failure (including Twilio not configured), logs the error and
    continues — the in_app record is always written regardless.
    """
    notif = models.Notification(
        recipient_user_id=recipient_user_id,
        notification_type=notification_type,
        title=title,
        body=body,
        severity=severity,
        related_entity_type=related_entity_type,
        related_entity_id=str(related_entity_id) if related_entity_id is not None else None,
        channel=channel,
        is_read=False,
        created_at=datetime.utcnow(),
    )
    db.add(notif)
    db.flush()   # assigns notif.id, consistent with audit_service.log_event pattern

    if send_whatsapp and recipient_user_id:
        try:
            from app.services import whatsapp_service
            user = db.query(models.User).get(recipient_user_id)
            if user and user.whatsapp_number:
                whatsapp_service.send_message(
                    to=user.whatsapp_number,
                    body=f"*{title}*\n{body}",
                )
                notif.sent_at = datetime.utcnow()
                db.flush()
        except Exception as exc:
            # Never crash the caller because of an optional delivery channel.
            logger.warning(f"WhatsApp delivery failed for notification #{notif.id}: {exc}")

    return notif


def has_recent_notification(
    db: Session,
    *,
    notification_type: str,
    related_entity_type: str,
    related_entity_id: str,
    within_hours: int = NOTIFICATION_DEDUP_HOURS,
) -> bool:
    """
    Deduplication check: returns True if a notification of the same type
    for the same related entity was already created within the given window.
    Used by Celery tasks to avoid re-alerting for the same condition daily.
    """
    cutoff = datetime.utcnow() - timedelta(hours=within_hours)
    existing = (
        db.query(models.Notification)
        .filter(
            and_(
                models.Notification.notification_type == notification_type,
                models.Notification.related_entity_type == related_entity_type,
                models.Notification.related_entity_id == str(related_entity_id),
                models.Notification.created_at >= cutoff,
            )
        )
        .first()
    )
    return existing is not None


def get_notifications_for_user(
    db: Session,
    user: models.User,
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> list[models.Notification]:
    """
    Returns notifications for a given user: those explicitly addressed to
    them (recipient_user_id=user.id) PLUS broadcast notifications
    (recipient_user_id=None) for owners.

    Staff only see their own notifications (broadcast is owner-only by
    convention — the tasks that create broadcast notifications are all
    owner-facing alerts like TrustChain tamper and daily digests).
    """
    q = db.query(models.Notification)

    if user.role == "owner":
        q = q.filter(
            (models.Notification.recipient_user_id == user.id) |
            (models.Notification.recipient_user_id.is_(None))
        )
    else:
        q = q.filter(models.Notification.recipient_user_id == user.id)

    if unread_only:
        q = q.filter(models.Notification.is_read.is_(False))

    return (
        q.order_by(desc(models.Notification.created_at))
        .offset(offset)
        .limit(limit)
        .all()
    )


def get_unread_count(db: Session, user: models.User) -> int:
    """Fast unread count for the NavBar badge — single COUNT query."""
    q = db.query(models.Notification).filter(models.Notification.is_read.is_(False))

    if user.role == "owner":
        q = q.filter(
            (models.Notification.recipient_user_id == user.id) |
            (models.Notification.recipient_user_id.is_(None))
        )
    else:
        q = q.filter(models.Notification.recipient_user_id == user.id)

    return q.count()


def mark_read(db: Session, notification_id: int, user: models.User) -> Optional[models.Notification]:
    """
    Marks one notification as read. Returns None if not found or if the
    notification doesn't belong to the requesting user (no 403 — just a
    no-op, since the frontend can only call this for notifications it
    already fetched for the user).
    """
    notif = db.query(models.Notification).get(notification_id)
    if not notif:
        return None

    # Ownership check: can mark their own, or broadcast (null recipient) if owner
    is_mine = notif.recipient_user_id == user.id
    is_broadcast_for_owner = notif.recipient_user_id is None and user.role == "owner"
    if not (is_mine or is_broadcast_for_owner):
        return None

    notif.is_read = True
    db.commit()
    return notif


def mark_all_read(db: Session, user: models.User) -> int:
    """Marks all of the user's unread notifications as read. Returns count updated."""
    q = db.query(models.Notification).filter(models.Notification.is_read.is_(False))

    if user.role == "owner":
        q = q.filter(
            (models.Notification.recipient_user_id == user.id) |
            (models.Notification.recipient_user_id.is_(None))
        )
    else:
        q = q.filter(models.Notification.recipient_user_id == user.id)

    count = q.count()
    q.update({"is_read": True}, synchronize_session=False)
    db.commit()
    return count


def build_daily_digest(db: Session, user_id: int) -> dict:
    """
    Aggregates every pillar's urgent signals into one structured summary
    dict for the daily digest Celery task and for the CommandCenter
    (Priority 4).

    Deliberately honest about which components are "cheap" (simple DB
    counts) vs. "expensive" (forecast, chain verification):
      - Adherence alerts: one query over Sales + Customers — cheap
      - Outstanding credit: one query per customer (N+1 if unconstrained,
        but list_customers_with_outstanding_balance already limits to 100)
      - Near-expiry/low-stock counts: simple aggregate queries — cheap
      - Anomaly flags: IsolationForest on last-N rows — moderate, but the
        Celery task calls this, not the HTTP request path

    The TrustChain verify_chain call is deliberately NOT included here —
    verify_chain walks every entry in the ledger and is the one genuinely
    expensive operation. CommandCenter (Priority 4) handles it separately
    with its own cached result.
    """
    from app.services import customer_service, expiry_service, anomaly_service

    # 1. Adherence overdue alerts (consent-gated, see customer_service docstring)
    adherence_alerts = customer_service.compute_adherence_alerts(db)

    # 2. Outstanding credit — top 10 most overdue, sorted by amount desc
    outstanding = customer_service.list_customers_with_outstanding_balance(db, limit=10)

    # 3. Near-expiry: critical + expired batch count
    expiry_data = expiry_service.get_expiry_summary(db)
    near_expiry_critical_count = (expiry_data.get("expired", 0) + expiry_data.get("critical", 0))

    # 4. Low-stock count (medicines below threshold)
    from app import models as m
    low_stock_count = (
        db.query(m.Medicine)
        .filter(
            m.Medicine.low_stock_threshold.isnot(None),
            m.Medicine.current_stock < m.Medicine.low_stock_threshold,
        )
        .count()
    )

    # 5. Unresolved anomaly flags — price jump anomalies from last 30 days
    try:
        price_anomaly_result = anomaly_service.detect_price_jump_anomalies(db, days=30)
        anomaly_count = len(price_anomaly_result.get("anomalies", []))
    except Exception:
        anomaly_count = 0

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "user_id": user_id,
        "adherence_overdue_count": len(adherence_alerts),
        "adherence_alerts_sample": adherence_alerts[:5],    # first 5 for the digest message
        "outstanding_credit_total": sum(c["current_balance"] for c in outstanding),
        "outstanding_credit_customers": len(outstanding),
        "near_expiry_critical_count": near_expiry_critical_count,
        "low_stock_count": low_stock_count,
        "anomaly_flag_count": anomaly_count,
    }
