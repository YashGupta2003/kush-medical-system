"""
Celery background tasks for Kush Medical Hall.

Priority 1 new tasks:
  run_adherence_check_task    — daily adherence scan, fires AdherenceAlertRaisedEvent
  run_anomaly_scan_task       — daily anomaly scan, fires AnomalyFlaggedEvent
  send_daily_digest_task      — builds and delivers digest to all owner accounts
  publish_near_expiry_task    — publishes near-expiry listings to inter-pharmacy network
  compute_smart_thresholds_task — computes reorder thresholds for all medicines

Design decision — deduplication for adherence/anomaly alerts:
  Each Celery task checks notification_service.has_recent_notification() before
  firing an event, keyed on (notification_type, related_entity_type, related_entity_id).
  This prevents re-alerting for the same condition daily without a separate dedup
  table — the notifications table itself IS the dedup state.
"""
from datetime import datetime, timedelta, timezone
import traceback

from app.celery_app import celery_app
from app.database import SessionLocal
from app import models
from app.config import settings
from app.services import image_preprocessing
from app.services.ocr_service import run_ocr
from app.services.bill_parser import parse_bill_words
from app.services.cost_calculator import compute_cost_per_unit, cross_check_amount
from app.services.matcher import find_best_match


@celery_app.task(bind=True, name="process_bill")
def process_bill_task(self, bill_id: int):
    from app.services.pipeline import BillProcessingPipeline
    db = SessionLocal()
    try:
        task_id = getattr(self.request, "id", None)
        pipeline = BillProcessingPipeline(bill_id=bill_id, db=db, task_id=task_id)
        return pipeline.run()
    finally:
        db.close()


@celery_app.task(name="reprocess_region")
def reprocess_region_task(bill_id: int, x0: int, y0: int, x1: int, y1: int) -> dict:
    db = SessionLocal()
    try:
        bill = db.get(models.Bill, bill_id)
        if not bill:
            return {"status": "error", "detail": "Bill not found"}
        with open(bill.image_path, "rb") as f:
            original_bytes = f.read()
        crop_bytes = image_preprocessing.crop_region(original_bytes, x0, y0, x1, y1)
        result = run_ocr(crop_bytes)
        text = result.full_text.strip()
        return {"status": "ok", "text": text, "confidence": round(result.avg_confidence, 1)}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
    finally:
        db.close()


@celery_app.task(bind=True, name="rebuild_graph")
def rebuild_graph_task(self):
    from app.services import graph_service
    import redis

    r = redis.from_url(settings.redis_url)
    lock = r.lock("lock:rebuild_graph", timeout=600)
    
    if not lock.acquire(blocking=False):
        return {"status": "skipped", "reason": "Another rebuild is currently in progress."}

    db = SessionLocal()
    try:
        stats = graph_service.rebuild_full_graph(db)
        return {"status": "ok", "stats": stats}
    except Exception as e:
        db.rollback()
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()
        try:
            lock.release()
        except redis.exceptions.LockError:
            pass


# ---------------------------------------------------------------------------
# Priority 1 — Notification Engine scheduled tasks
# ---------------------------------------------------------------------------

@celery_app.task(name="run_adherence_check")
def run_adherence_check_task() -> dict:
    """
    Daily adherence check (6am IST via beat_schedule in celery_app.py).

    Calls customer_service.compute_adherence_alerts() to get every overdue
    (customer, medicine) pair, then for each one that hasn't been notified
    in the last 7 days, fires AdherenceAlertRaisedEvent via the event bus.

    The 7-day deduplication check uses notification_service.has_recent_notification()
    with the related_entity fields encoding "customer:{id}:medicine" + medicine_id,
    matching how handle_adherence_alert in subscribers.py writes the notification.
    """
    from app.services import customer_service, notification_service
    from app.events.bus import event_bus
    from app.events.events import AdherenceAlertRaisedEvent

    db = SessionLocal()
    fired = 0
    skipped = 0
    errors = 0

    try:
        alerts = customer_service.compute_adherence_alerts(db)

        for alert in alerts:
            try:
                # Dedup check — don't re-fire for the same pair within 7 days
                already_notified = notification_service.has_recent_notification(
                    db,
                    notification_type="adherence_overdue",
                    related_entity_type=f"customer:{alert['customer_id']}:medicine",
                    related_entity_id=str(alert["medicine_id"]),
                    within_hours=7 * 24,
                )
                if already_notified:
                    skipped += 1
                    continue

                event_bus.publish(AdherenceAlertRaisedEvent(
                    customer_id=alert["customer_id"],
                    customer_name=alert.get("customer_name"),
                    customer_phone=alert["customer_phone"],
                    medicine_id=alert["medicine_id"],
                    medicine_name=alert["medicine_name"],
                    days_overdue=alert["days_overdue"],
                    avg_gap_days=alert["avg_gap_days"],
                    db=db,
                ))
                db.commit()
                fired += 1
            except Exception as exc:
                db.rollback()
                errors += 1
                # Log but continue — one failed alert shouldn't stop the rest
                from app.core.logging import get_logger
                get_logger("tasks").warning(f"Adherence alert failed for customer {alert.get('customer_id')}: {exc}")

        return {"status": "ok", "alerts_found": len(alerts), "fired": fired, "skipped_dedup": skipped, "errors": errors}
    except Exception as e:
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()


@celery_app.task(name="run_anomaly_scan")
def run_anomaly_scan_task() -> dict:
    """
    Daily anomaly scan (6:15am IST via beat_schedule).

    Runs both anomaly detectors (price jumps + stock adjustments) and fires
    AnomalyFlaggedEvent for each new anomaly not notified today (24h dedup window
    — anomalies are more urgent than adherence alerts, so 24h is appropriate).
    """
    from app.services import anomaly_service, notification_service
    from app.events.bus import event_bus
    from app.events.events import AnomalyFlaggedEvent

    db = SessionLocal()
    fired = 0
    skipped = 0

    try:
        # Price jump anomalies (last 90 days)
        price_result = anomaly_service.detect_price_jump_anomalies(db, days=90)
        for anomaly in price_result.get("anomalies", []):
            medicine_id = anomaly.get("medicine_id")
            if not medicine_id:
                continue

            already = notification_service.has_recent_notification(
                db,
                notification_type="anomaly_flagged",
                related_entity_type="anomaly:price_jump:medicine",
                related_entity_id=str(medicine_id),
                within_hours=24,
            )
            if already:
                skipped += 1
                continue

            event_bus.publish(AnomalyFlaggedEvent(
                anomaly_type="price_jump",
                medicine_id=medicine_id,
                medicine_name=anomaly.get("medicine_name", "Unknown"),
                score=anomaly.get("score", 0.0),
                detail=anomaly,
                db=db,
            ))
            db.commit()
            fired += 1

        # Stock adjustment anomalies (last 90 days)
        stock_result = anomaly_service.detect_stock_adjustment_anomalies(db, days=90)
        for anomaly in stock_result.get("flagged_adjustments", []):
            medicine_id = anomaly.get("medicine_id")
            if not medicine_id:
                continue

            already = notification_service.has_recent_notification(
                db,
                notification_type="anomaly_flagged",
                related_entity_type="anomaly:stock_adjustment:medicine",
                related_entity_id=str(medicine_id),
                within_hours=24,
            )
            if already:
                skipped += 1
                continue

            event_bus.publish(AnomalyFlaggedEvent(
                anomaly_type="stock_adjustment",
                medicine_id=medicine_id,
                medicine_name=anomaly.get("medicine_name", "Unknown"),
                score=anomaly.get("score", 0.0),
                detail=anomaly,
                db=db,
            ))
            db.commit()
            fired += 1

        return {"status": "ok", "fired": fired, "skipped_dedup": skipped}
    except Exception as e:
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()


@celery_app.task(name="send_daily_digest")
def send_daily_digest_task() -> dict:
    """
    Daily digest (8am IST via beat_schedule).

    Builds the digest for every owner account and creates a daily_digest
    notification for each. Also attempts WhatsApp delivery if the owner
    has a whatsapp_number configured.
    """
    from app.services import notification_service, whatsapp_service

    db = SessionLocal()
    sent = 0
    errors = 0

    try:
        owners = db.query(models.User).filter(
            models.User.role == "owner",
            models.User.is_active.is_(True),
        ).all()

        for owner in owners:
            try:
                digest = notification_service.build_daily_digest(db, owner.id)
                body_lines = [
                    f"📊 Adherence overdue: {digest['adherence_overdue_count']} customers",
                    f"💳 Outstanding credit: ₹{digest['outstanding_credit_total']:.0f} ({digest['outstanding_credit_customers']} customers)",
                    f"⏳ Near-expiry critical: {digest['near_expiry_critical_count']}",
                    f"📦 Low stock items: {digest['low_stock_count']}",
                    f"🚨 Anomaly flags: {digest['anomaly_flag_count']}",
                ]
                notification_service.create_notification(
                    db,
                    notification_type="daily_digest",
                    title="Daily Summary — Kush Medical Hall",
                    body="\n".join(body_lines),
                    severity="info",
                    recipient_user_id=owner.id,
                    channel="in_app",
                )
                db.commit()

                # Best-effort WhatsApp delivery
                if owner.whatsapp_number:
                    whatsapp_service.send_digest(owner.whatsapp_number, digest)

                sent += 1
            except Exception as exc:
                db.rollback()
                errors += 1
                from app.core.logging import get_logger
                get_logger("tasks").warning(f"Digest failed for owner {owner.id}: {exc}")

        return {"status": "ok", "digests_sent": sent, "errors": errors}
    except Exception as e:
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()


@celery_app.task(name="publish_near_expiry_listings")
def publish_near_expiry_listings_task(days: int = 60) -> dict:
    """
    Daily near-expiry listing publisher (7am IST via beat_schedule).
    Publishes expiring-soon batches to the inter-pharmacy network.
    Reuses the existing network_service.publish_near_expiry_listings() function.
    """
    from app.services import network_service

    db = SessionLocal()
    try:
        result = network_service.publish_near_expiry_listings(db, days=days)
        db.commit()
        return {"status": "ok", "published_count": len(result)}
    except Exception as e:
        db.rollback()
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()


@celery_app.task(name="compute_smart_thresholds_bulk")
def compute_smart_thresholds_bulk_task() -> dict:
    """
    Daily smart threshold computation (5am IST via beat_schedule).
    Runs reorder_intelligence.compute_smart_threshold for every medicine,
    updating suggested_low_stock_threshold.
    """
    from app.services import reorder_intelligence

    db = SessionLocal()
    updated = 0
    errors = 0

    try:
        medicines = db.query(models.Medicine).all()
        for medicine in medicines:
            try:
                result = reorder_intelligence.compute_smart_threshold(db, medicine.id)
                if result.get("has_sufficient_data"):
                    medicine.suggested_low_stock_threshold = result.get("suggested_threshold")
                    medicine.avg_daily_sales_30d = result.get("avg_daily_sales_30d")
                    # BUG FIX: 'from datetime import datetime' was inside the loop — moved to module top
                    medicine.suggestion_computed_at = datetime.now(timezone.utc)
                    updated += 1
            except Exception:
                errors += 1

        db.commit()
        return {"status": "ok", "updated": updated, "errors": errors, "total": len(medicines)}
    except Exception as e:
        db.rollback()
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# BUG FIX #3 — Zombie Bill Cleanup (runs every 10 minutes via beat_schedule)
# ---------------------------------------------------------------------------
# If a Celery worker crashes (OOM, Redis outage, oversized OCR image), the
# bill stays in 'queued' or 'processing' forever — the frontend shows
# 'Processing...' for eternity. This task marks those stale bills as 'failed'
# after ZOMBIE_BILL_TIMEOUT_MINUTES so the user knows to re-upload.

# BUG FIX: 10 minutes was too aggressive — a large bill image with many line
# items can legitimately take more than 10 minutes for OCR + parsing on a
# slow server. 30 minutes is a safer threshold to avoid false failure marking.
ZOMBIE_BILL_TIMEOUT_MINUTES = 30


@celery_app.task(name="cleanup_zombie_bills")
def cleanup_zombie_bills_task() -> dict:
    """
    BUG FIX #3: Zombie Bill Cleanup.
    Runs every 10 minutes (via Celery Beat). Finds all bills stuck in
    'queued' or 'processing' state for longer than ZOMBIE_BILL_TIMEOUT_MINUTES
    and marks them as 'failed' with a descriptive processing_error.

    Root cause this fixes: if a Celery worker running process_bill_task is
    killed mid-execution (OOM, Redis crash, SIGKILL), the bill.status is never
    updated from 'processing' and stays frozen in that state permanently.
    """
    from app.core.logging import get_logger
    log = get_logger("cleanup_zombie_bills")

    db = SessionLocal()
    killed = 0
    errors = 0

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=ZOMBIE_BILL_TIMEOUT_MINUTES)

        zombie_bills = (
            db.query(models.Bill)
            .filter(
                models.Bill.status.in_(["queued", "processing"]),
                models.Bill.uploaded_at <= cutoff,
            )
            .all()
        )

        for bill in zombie_bills:
            try:
                bill.status = "failed"
                bill.processing_error = (
                    f"Bill processing timed out after {ZOMBIE_BILL_TIMEOUT_MINUTES} minutes. "
                    f"The OCR worker may have crashed (e.g. OOM or Redis failure). "
                    f"Please re-upload the bill."
                )
                db.commit()
                killed += 1
                log.warning(
                    f"[ZOMBIE CLEANUP] Bill #{bill.id} was stuck in 'queued/processing' since "
                    f"{bill.uploaded_at} — marked as failed."
                )
            except Exception as exc:
                db.rollback()
                errors += 1
                log.error(f"[ZOMBIE CLEANUP] Failed to mark bill #{bill.id} as failed: {exc}")

        return {
            "status": "ok",
            "zombie_bills_found": len(zombie_bills),
            "marked_failed": killed,
            "errors": errors,
        }
    except Exception as e:
        db.rollback()
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# BUG FIX #4 — Old Upload File Cleanup (nightly at 3am via beat_schedule)
# ---------------------------------------------------------------------------
# bill photos accumulate in backend/uploads/ forever. Without cleanup, the
# server disk fills up in ~1-2 years. This task deletes image files that are
# older than UPLOAD_RETENTION_DAYS. The Bill DB row is preserved for history.

UPLOAD_RETENTION_DAYS = 90  # delete image files older than this many days


@celery_app.task(name="cleanup_old_upload_files")
def cleanup_old_upload_files_task() -> dict:
    """
    BUG FIX #4: Disk Space Exhaustion Prevention.
    Runs nightly at 3am (via Celery Beat). Deletes bill image files from disk
    that are older than UPLOAD_RETENTION_DAYS (default: 90 days).

    - The Bill DB row is preserved (invoice history, status, amounts, etc.).
    - Only the raw image file (bill.image_path) is deleted from disk.
    - After deletion, bill.image_path is set to None so the image endpoint
      returns 404 gracefully instead of a broken file path.

    Root cause this fixes: uploaded photos accumulate forever in backend/uploads/
    with no cleanup mechanism. A pharmacy processing 10 bills/day will exhaust
    a typical 256GB server disk in under 2 years.
    """
    import os
    from app.core.logging import get_logger
    log = get_logger("cleanup_old_upload_files")

    db = SessionLocal()
    deleted = 0
    missing = 0
    errors = 0

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=UPLOAD_RETENTION_DAYS)

        old_bills = (
            db.query(models.Bill)
            .filter(
                models.Bill.uploaded_at <= cutoff,
                models.Bill.image_path.isnot(None),
            )
            .all()
        )

        for bill in old_bills:
            try:
                path = bill.image_path
                if path and os.path.exists(path):
                    os.remove(path)
                    deleted += 1
                    log.info(f"[UPLOAD CLEANUP] Deleted {path} (Bill #{bill.id}, uploaded {bill.uploaded_at})")
                else:
                    missing += 1  # file already gone — just clear the DB path

                # Clear the path so the image endpoint returns 404, not an error
                bill.image_path = None
            except Exception as exc:
                errors += 1
                log.error(f"[UPLOAD CLEANUP] Failed to delete file for Bill #{bill.id}: {exc}")

        db.commit()
        return {
            "status": "ok",
            "retention_days": UPLOAD_RETENTION_DAYS,
            "old_bills_found": len(old_bills),
            "files_deleted": deleted,
            "files_already_missing": missing,
            "errors": errors,
        }
    except Exception as e:
        db.rollback()
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()

@celery_app.task(name="run_surveillance_scan")
def run_surveillance_scan_task() -> dict:
    """Daily surveillance spike detection (runs after sales close)."""
    from app.database import SessionLocal
    from app.services import surveillance_service
    db = SessionLocal()
    try:
        spikes = surveillance_service.detect_spikes(db)
        # Event is fired inside detect_spikes
        return {"status": "ok", "spikes_detected": len(spikes)}
    except Exception as e:
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()

@celery_app.task(name='generate_smart_purchase_order')
def generate_smart_purchase_order_task() -> dict:
    import json
    from app.services.smart_purchase_service import generate_purchase_order
    from app.core.cache import get_redis_client
    db = SessionLocal()
    try:
        result = generate_purchase_order(db)
        r = get_redis_client()
        if r:
            r.setex("smart_purchase:latest", 7 * 24 * 60 * 60, json.dumps(result))
        return {"status": "ok", "items_count": result.get("items_count")}
    except Exception as e:
        db.rollback()
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()
