"""
Subscribers / Event Handlers for Domain Events.
Decouples domain actions (stock update, rate history, batch creation, caching, learning,
tamper-evident audit logging) from API controllers and background tasks.

Priority 1 additions (Notification Engine):
  - handle_low_stock_crossed    — creates an in-app notification when medicine crosses below threshold
  - handle_adherence_alert      — creates an adherence overdue notification (with WhatsApp option)
  - handle_anomaly_flagged      — creates an anomaly flag notification for owners
  - handle_credit_overdue       — creates a credit overdue notification
"""
from datetime import datetime
from typing import List
from app.core.logging import get_logger
from app.events.bus import event_bus
from app.events.events import (
    BillConfirmedEvent,
    BillUploadedEvent,
    BillProcessedEvent,
    StockUpdatedEvent,
    RateChangedEvent,
    LowStockCrossedEvent,
    AdherenceAlertRaisedEvent,
    AnomalyFlaggedEvent,
    CreditOverdueEvent,
    ColdChainExcursionEvent,
    SurveillanceSpikeDetectedEvent,
)
from app import models, schemas
from app.services.cost_calculator import compute_cost_per_unit
from app.services.matcher import save_learned_mapping
from app.services import stock_service, expiry_service, graph_service, audit_service
from app.core.cache import invalidate_analytics_cache

logger = get_logger("event_subscribers")


def handle_bill_confirmed_rate_history(event: BillConfirmedEvent) -> None:
    """
    Subscriber: Computes landed unit costs, updates master rate list,
    logs rate change history audit entries, and appends a matching
    tamper-evident 'rate_change' entry to TrustChain's ledger for every
    rate/MRP change (Pillar 4).
    """
    logger.info(f"[SUBSCRIBER: RateHistory] Processing rate updates for Bill #{event.bill_id}")
    db = event.db
    bill = db.query(models.Bill).get(event.bill_id)
    if not bill:
        return

    items_by_id = {item.id: item for item in bill.items}
    changes_collector = getattr(event, "changes_output", None)

    for edit in event.items_edits:
        item = items_by_id.get(edit.id)
        if item is None:
            continue

        for attr in ("raw_name", "qty", "free_qty", "mrp", "rate",
                     "discount_pct", "special_discount_pct", "gst_pct", "exp_date"):
            value = getattr(edit, attr, None)
            if value is not None:
                setattr(item, attr, value)

        item.computed_cost_per_unit = compute_cost_per_unit(
            rate=float(item.rate or 0), qty=float(item.qty or 0),
            discount_pct=float(item.discount_pct or 0),
            special_discount_pct=float(item.special_discount_pct or 0),
            gst_pct=float(item.gst_pct or 0), free_qty=float(item.free_qty or 0),
        )

        if edit.medicine_id:
            item.medicine_id = edit.medicine_id
            item.match_status = "manual"

        item.match_status = "confirmed" if item.match_status != "unmatched" else "unmatched"

        if edit.apply_to_master_list and item.medicine_id:
            medicine = db.query(models.Medicine).get(item.medicine_id)
            if medicine:
                old_rate, old_mrp = medicine.net_rate, medicine.mrp
                new_rate = item.computed_cost_per_unit
                new_mrp = item.mrp if item.mrp is not None else medicine.mrp

                old_rate_f = float(old_rate) if old_rate is not None else None
                old_mrp_f = float(old_mrp) if old_mrp is not None else None
                new_rate_f = float(new_rate) if new_rate is not None else None
                new_mrp_f = float(new_mrp) if new_mrp is not None else None

                rate_changed = old_rate_f != new_rate_f
                mrp_changed = old_mrp_f != new_mrp_f

                if rate_changed or mrp_changed:
                    history = models.RateHistory(
                        medicine_id=medicine.id, bill_item_id=item.id,
                        old_net_rate=old_rate, new_net_rate=new_rate,
                        old_mrp=old_mrp, new_mrp=new_mrp,
                    )
                    db.add(history)
                    db.flush()  # need history.id before it can be the audit entry's reference_id

                    # --- TrustChain (Pillar 4): tamper-evident record of this rate change ---
                    audit_service.log_event(db, "rate_change", history.id, {
                        "medicine_id": medicine.id,
                        "medicine_name": medicine.particulars,
                        "bill_item_id": item.id,
                        "bill_id": bill.id,
                        "old_net_rate": old_rate_f, "new_net_rate": new_rate_f,
                        "old_mrp": old_mrp_f, "new_mrp": new_mrp_f,
                    })

                    if rate_changed and changes_collector is not None:
                        changes_collector.append(schemas.ChangeSummaryItem(
                            medicine_name=medicine.particulars, field="net_rate",
                            old_value=old_rate_f, new_value=new_rate_f,
                        ))
                    if mrp_changed and changes_collector is not None:
                        changes_collector.append(schemas.ChangeSummaryItem(
                            medicine_name=medicine.particulars, field="mrp",
                            old_value=old_mrp_f, new_value=new_mrp_f,
                        ))
                    medicine.net_rate = new_rate
                    medicine.mrp = new_mrp


def handle_bill_confirmed_learning(event: BillConfirmedEvent) -> None:
    """
    Subscriber: Learns manually confirmed distributor-medicine mappings.
    """
    logger.info(f"[SUBSCRIBER: Learning] Updating learned mappings for Bill #{event.bill_id}")
    db = event.db
    bill = db.query(models.Bill).get(event.bill_id)
    if not bill:
        return

    items_by_id = {item.id: item for item in bill.items}
    for edit in event.items_edits:
        item = items_by_id.get(edit.id)
        if item and edit.medicine_id:
            save_learned_mapping(
                db, raw_name=item.raw_name, medicine_id=edit.medicine_id,
                distributor_id=bill.distributor_id,
            )


def handle_bill_confirmed_stock(event: BillConfirmedEvent) -> None:
    """
    Subscriber: Increments inventory physical stock for confirmed bill items.
    """
    logger.info(f"[SUBSCRIBER: Stock] Incrementing stock for confirmed items on Bill #{event.bill_id}")
    db = event.db
    bill = db.query(models.Bill).get(event.bill_id)
    if not bill:
        return

    for item in bill.items:
        if item.medicine_id:
            stock_service.add_stock_from_confirmed_bill_item(db, item)


def handle_bill_confirmed_expiry(event: BillConfirmedEvent) -> None:
    """
    Subscriber: Creates medicine batch / expiry records for confirmed bill items.
    Each batch creation also appends a 'batch_received' TrustChain entry
    (see expiry_service.create_batch_from_confirmed_item, Pillar 4).
    """
    logger.info(f"[SUBSCRIBER: Expiry] Creating batch/expiry entries for Bill #{event.bill_id}")
    db = event.db
    bill = db.query(models.Bill).get(event.bill_id)
    if not bill:
        return

    for item in bill.items:
        if item.medicine_id:
            expiry_service.create_batch_from_confirmed_item(db, item)

def handle_bill_confirmed_graph_sync(event: BillConfirmedEvent) -> None:
    """
    Subscriber: Keeps PharmaGraph's SUPPLIES edges (distributor -> medicine)
    live - cheap (one edge per matched item), so synced on every confirm
    rather than waiting for the periodic full graph rebuild. See
    app/services/graph_service.py for the full PharmaGraph design.
    """
    logger.info(f"[SUBSCRIBER: PharmaGraph] Syncing SUPPLIES edges for Bill #{event.bill_id}")
    db = event.db
    bill = db.query(models.Bill).get(event.bill_id)
    if not bill:
        return

    for item in bill.items:
        if item.medicine_id:
            graph_service.sync_supplies_edge(db, bill.distributor_id, item.medicine_id)


def handle_bill_confirmed_cache_invalidation(event: BillConfirmedEvent) -> None:
    """
    Subscriber: Invalidates cached analytics, dashboard, and GST reports upon confirmation.
    """
    logger.info(f"[SUBSCRIBER: CacheInvalidation] Flushed analytics caches for Bill #{event.bill_id}")
    invalidate_analytics_cache()


def handle_bill_confirmed_audit_log(event: BillConfirmedEvent) -> None:
    """
    Subscriber: TrustChain (Pillar 4) - appends ONE top-level 'bill_confirmed'
    entry to the tamper-evident ledger per confirmed bill, independent of
    the more granular 'rate_change' and 'batch_received' entries the other
    subscribers above already log for the same confirm action.

    Registered LAST so it reads the bill's fully-processed state (item
    count, total_amount) after every other subscriber has run - though
    since it re-queries the DB fresh, correctness doesn't actually depend
    on subscriber ordering, only the readability of the snapshot does.
    """
    logger.info(f"[SUBSCRIBER: TrustChain] Logging bill_confirmed audit entry for Bill #{event.bill_id}")
    db = event.db
    bill = db.query(models.Bill).get(event.bill_id)
    if not bill:
        return

    audit_service.log_event(db, "bill_confirmed", bill.id, {
        "bill_id": bill.id,
        "distributor_id": bill.distributor_id,
        "invoice_no": bill.invoice_no,
        "total_amount": float(bill.total_amount) if bill.total_amount is not None else None,
        "item_count": len(bill.items),
        "matched_item_count": sum(1 for i in bill.items if i.medicine_id),
        "confirmed_at": datetime.utcnow().isoformat(),
    })


def handle_bill_uploaded_logging(event: BillUploadedEvent) -> None:
    """
    Subscriber: Logs bill upload events.
    """
    logger.info(
        f"[EVENT: BillUploaded] Bill #{event.bill_id} ({event.filename}) "
        f"distributor={event.distributor_name} checksum={event.checksum}"
    )


def handle_bill_processed_logging(event: BillProcessedEvent) -> None:
    """
    Subscriber: Logs OCR processing pipeline output.
    """
    logger.info(
        f"[EVENT: BillProcessed] Bill #{event.bill_id} status={event.status} "
        f"ocr_confidence={event.ocr_confidence}% items={event.items_count}"
    )


# ---------------------------------------------------------------------------
# Priority 1 — Notification Engine subscribers
# ---------------------------------------------------------------------------

def handle_low_stock_crossed(event: LowStockCrossedEvent) -> None:
    """
    Subscriber: Creates an in-app (and optionally WhatsApp) notification when
    a medicine's stock crosses below its low_stock_threshold.

    Runs in the same transaction as the ledger entry that triggered the
    crossing — same pattern as handle_bill_confirmed_audit_log writing
    to the TrustChain in the same transaction as the bill confirmation.
    The notification is committed when the enclosing stock_service transaction
    commits (stock_service._add_ledger_entry calls db.flush() but not commit
    for this path — the commit happens in record_sale or record_adjustment).
    """
    logger.info(
        f"[SUBSCRIBER: LowStock] Medicine '{event.medicine_name}' crossed below "
        f"threshold ({event.new_balance:.1f} < {event.threshold:.1f})"
    )
    from app.services import notification_service

    notification_service.create_notification(
        event.db,
        notification_type="low_stock_crossed",
        title=f"Low Stock Alert: {event.medicine_name}",
        body=(
            f"Stock has dropped to {event.new_balance:.0f} units "
            f"(threshold: {event.threshold:.0f}). "
            f"Consider placing a reorder."
        ),
        severity="warning",
        recipient_user_id=None,   # broadcast to all owners
        related_entity_type="medicine",
        related_entity_id=str(event.medicine_id),
        channel="in_app",
    )


def handle_adherence_alert(event: AdherenceAlertRaisedEvent) -> None:
    """
    Subscriber: Creates a notification for an overdue adherence alert.
    The Celery task has already checked deduplication (7-day window) before
    firing this event, so this subscriber always creates the notification
    without a further dedup check.
    """
    logger.info(
        f"[SUBSCRIBER: Adherence] Alert for customer #{event.customer_id} "
        f"({event.customer_phone}) on {event.medicine_name}"
    )
    from app.services import notification_service

    customer_label = event.customer_name or event.customer_phone
    notification_service.create_notification(
        event.db,
        notification_type="adherence_overdue",
        title=f"Refill Overdue: {customer_label}",
        body=(
            f"{customer_label} is {event.days_overdue:.0f} days overdue for "
            f"{event.medicine_name} (typical gap: {event.avg_gap_days:.0f} days). "
            f"Consider a follow-up call."
        ),
        severity="warning",
        recipient_user_id=None,   # broadcast to owners
        related_entity_type=f"customer:{event.customer_id}:medicine",
        related_entity_id=str(event.medicine_id),
        channel="in_app",
    )


def handle_anomaly_flagged(event: AnomalyFlaggedEvent) -> None:
    """
    Subscriber: Creates an owner-only notification for a newly flagged anomaly.
    """
    logger.info(
        f"[SUBSCRIBER: Anomaly] {event.anomaly_type} anomaly on "
        f"medicine #{event.medicine_id} ({event.medicine_name}), score={event.score:.2f}"
    )
    from app.services import notification_service

    type_label = "price jump" if event.anomaly_type == "price_jump" else "stock adjustment"
    notification_service.create_notification(
        event.db,
        notification_type="anomaly_flagged",
        title=f"Anomaly Detected: {event.medicine_name}",
        body=(
            f"An unusual {type_label} was detected for {event.medicine_name} "
            f"(anomaly score: {event.score:.2f}). "
            f"Review in Predictive Intelligence → Anomalies."
        ),
        severity="critical",
        recipient_user_id=None,   # owner broadcast
        related_entity_type=f"anomaly:{event.anomaly_type}:medicine",
        related_entity_id=str(event.medicine_id),
        channel="in_app",
    )


def handle_credit_overdue(event: CreditOverdueEvent) -> None:
    """
    Subscriber: Creates a notification for a customer with a long-overdue
    credit balance.
    """
    logger.info(
        f"[SUBSCRIBER: Credit] Customer #{event.customer_id} "
        f"({event.customer_phone}) has ₹{event.outstanding_amount:.0f} outstanding"
    )
    from app.services import notification_service

    customer_label = event.customer_name or event.customer_phone
    notification_service.create_notification(
        event.db,
        notification_type="credit_overdue",
        title=f"Udhaar Outstanding: {customer_label}",
        body=(
            f"{customer_label} has ₹{event.outstanding_amount:.0f} outstanding credit. "
            f"Check the Customers screen to follow up."
        ),
        severity="info",
        recipient_user_id=None,
        related_entity_type="customer",
        related_entity_id=str(event.customer_id),
        channel="in_app",
    )

def handle_cold_chain_excursion(event: ColdChainExcursionEvent) -> None:
    from app.services import notification_service
    direction = "above" if event.recorded_temp_c > event.max_temp_c else "below"
    notification_service.create_notification(
        event.db,
        notification_type="system",
        title=f"⚠️ Cold Chain Excursion: {event.unit_label}",
        body=(
            f"Temperature reading of {event.recorded_temp_c}°C is {direction} "
            f"the safe range ({event.min_temp_c}–{event.max_temp_c}°C). "
            f"Check the unit immediately and review stored medicines."
        ),
        severity="critical",
        recipient_user_id=None,
        related_entity_type="cold_chain_unit",
        related_entity_id=str(event.unit_id),
        channel="in_app",
    )

def register_all_subscribers() -> None:
    """
    Registers all application domain subscribers with the global EventBus.
    """
    # --- Existing BillConfirmed pipeline (7 subscribers, registered in order) ---
    event_bus.subscribe(BillConfirmedEvent, handle_bill_confirmed_rate_history)
    event_bus.subscribe(BillConfirmedEvent, handle_bill_confirmed_learning)
    event_bus.subscribe(BillConfirmedEvent, handle_bill_confirmed_stock)
    event_bus.subscribe(BillConfirmedEvent, handle_bill_confirmed_expiry)
    event_bus.subscribe(BillConfirmedEvent, handle_bill_confirmed_graph_sync)
    event_bus.subscribe(BillConfirmedEvent, handle_bill_confirmed_cache_invalidation)
    event_bus.subscribe(BillConfirmedEvent, handle_bill_confirmed_audit_log)

    # --- Logging subscribers ---
    event_bus.subscribe(BillUploadedEvent, handle_bill_uploaded_logging)
    event_bus.subscribe(BillProcessedEvent, handle_bill_processed_logging)

    # --- Priority 1: Notification Engine subscribers ---
    event_bus.subscribe(LowStockCrossedEvent, handle_low_stock_crossed)
    event_bus.subscribe(AdherenceAlertRaisedEvent, handle_adherence_alert)
    event_bus.subscribe(AnomalyFlaggedEvent, handle_anomaly_flagged)
    event_bus.subscribe(CreditOverdueEvent, handle_credit_overdue)
    event_bus.subscribe(ColdChainExcursionEvent, handle_cold_chain_excursion)

    logger.info("All domain event subscribers successfully registered with EventBus.")