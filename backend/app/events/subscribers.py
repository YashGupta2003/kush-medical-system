"""
Subscribers / Event Handlers for Domain Events.
Decouples domain actions (stock update, rate history, batch creation, caching, learning)
from API controllers and background tasks.
"""
from typing import List
from app.core.logging import get_logger
from app.events.bus import event_bus
from app.events.events import (
    BillConfirmedEvent,
    BillUploadedEvent,
    BillProcessedEvent,
    StockUpdatedEvent,
    RateChangedEvent,
)
from app import models, schemas
from app.services.cost_calculator import compute_cost_per_unit
from app.services.matcher import save_learned_mapping
from app.services import stock_service, expiry_service
from app.core.cache import invalidate_analytics_cache

logger = get_logger("event_subscribers")


def handle_bill_confirmed_rate_history(event: BillConfirmedEvent) -> None:
    """
    Subscriber: Computes landed unit costs, updates master rate list,
    and logs rate change history audit entries.
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
                    db.add(models.RateHistory(
                        medicine_id=medicine.id, bill_item_id=item.id,
                        old_net_rate=old_rate, new_net_rate=new_rate,
                        old_mrp=old_mrp, new_mrp=new_mrp,
                    ))
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
    """
    logger.info(f"[SUBSCRIBER: Expiry] Creating batch/expiry entries for Bill #{event.bill_id}")
    db = event.db
    bill = db.query(models.Bill).get(event.bill_id)
    if not bill:
        return

    for item in bill.items:
        if item.medicine_id:
            expiry_service.create_batch_from_confirmed_item(db, item)


def handle_bill_confirmed_cache_invalidation(event: BillConfirmedEvent) -> None:
    """
    Subscriber: Invalidates cached analytics, dashboard, and GST reports upon confirmation.
    """
    logger.info(f"[SUBSCRIBER: CacheInvalidation] Flushed analytics caches for Bill #{event.bill_id}")
    invalidate_analytics_cache()


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


def register_all_subscribers() -> None:
    """
    Registers all application domain subscribers with the global EventBus.
    """
    event_bus.subscribe(BillConfirmedEvent, handle_bill_confirmed_rate_history)
    event_bus.subscribe(BillConfirmedEvent, handle_bill_confirmed_learning)
    event_bus.subscribe(BillConfirmedEvent, handle_bill_confirmed_stock)
    event_bus.subscribe(BillConfirmedEvent, handle_bill_confirmed_expiry)
    event_bus.subscribe(BillConfirmedEvent, handle_bill_confirmed_cache_invalidation)
    event_bus.subscribe(BillUploadedEvent, handle_bill_uploaded_logging)
    event_bus.subscribe(BillProcessedEvent, handle_bill_processed_logging)
    logger.info("All domain event subscribers successfully registered with EventBus.")
