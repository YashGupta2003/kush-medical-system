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
        bill = db.query(models.Bill).get(bill_id)
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

    db = SessionLocal()
    try:
        stats = graph_service.rebuild_full_graph(db)
        return {"status": "ok", "stats": stats}
    except Exception as e:
        db.rollback()
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()


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
                    from datetime import datetime
                    medicine.suggestion_computed_at = datetime.utcnow()
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
