"""
Notifications router — the HTTP interface for the Notification Engine (Priority 1).

Auth pattern follows existing precedent:
  - GET/PATCH endpoints: any logged-in user (get_current_user) — staff can see
    their own alerts, owners see everything including broadcast
  - POST /digest/send-now: owner-only — this triggers a manual Celery task,
    which is an admin-level operation
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.services import notification_service
from app.deps import get_current_user, require_owner

router = APIRouter(prefix="/notifications", tags=["notifications"])

_MAX_PAGE_SIZE = 100


@router.get("", response_model=schemas.PaginatedResponse[schemas.NotificationOut])
def list_notifications(
    unread_only: bool = False,
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(20, ge=1, le=_MAX_PAGE_SIZE, description="Items per page (max 100)"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Returns the current user's notifications (their own + broadcast
    if owner), paginated. Defaults to all (read + unread). Set
    unread_only=true for the notification-center panel view.
    Returns {items, total, page, page_size} — same shape as /medicines.
    """
    page_size = min(page_size, _MAX_PAGE_SIZE)
    offset = (page - 1) * page_size

    items, total = notification_service.get_notifications_for_user_paginated(
        db, current_user, unread_only=unread_only, limit=page_size, offset=offset
    )
    return schemas.PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/unread-count", response_model=schemas.UnreadCountOut)
def unread_count(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Fast unread count for the NavBar badge. Polled every 30s by the
    frontend. Returns a single integer, not a full notification list.
    """
    count = notification_service.get_unread_count(db, current_user)
    return {"count": count}


@router.patch("/{notification_id}/read", response_model=schemas.NotificationOut)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Marks a single notification as read. 404 if not found or not accessible."""
    notif = notification_service.mark_read(db, notification_id, current_user)
    if not notif:
        raise HTTPException(404, "Notification not found or not accessible")
    return notif


@router.post("/read-all", response_model=schemas.MarkAllReadOut)
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Marks all of the current user's unread notifications as read."""
    count = notification_service.mark_all_read(db, current_user)
    return {"marked_read": count}


@router.post("/digest/send-now")
def send_digest_now(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_owner),
):
    """
    Owner-only: triggers the daily digest Celery task immediately for
    every owner account. For demo / testing without waiting for the
    scheduled run. Returns task id so the caller can optionally poll status.
    """
    from app.services.tasks import send_daily_digest_task
    result = send_daily_digest_task.delay()
    return {"status": "queued", "task_id": result.id}
