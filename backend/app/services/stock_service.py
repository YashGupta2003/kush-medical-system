"""
Everything to do with stock quantity, sales, and the reorder list.

Priority 1 addition: _add_ledger_entry now fires LowStockCrossedEvent
when a medicine's stock crosses below its low_stock_threshold. The crossing
detection (old_balance >= threshold AND new_balance < threshold) ensures
the event fires exactly once at the moment of crossing, not on every
subsequent sale while already below threshold — preventing notification spam.
"""
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy import desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.core.domain_errors import ConflictError, NotFoundError, ValidationError
from app.services import audit_service, surveillance_service


def _to_decimal(value) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _supports_for_update(db: Session) -> bool:
    try:
        bind = db.get_bind()
        return bool(bind and bind.dialect.name not in ("sqlite",))
    except Exception:
        return False


def _get_medicine_for_update(db: Session, tenant_id: Optional[int], medicine_id: int) -> Optional[models.Medicine]:
    q = db.query(models.Medicine).filter(models.Medicine.id == medicine_id)
    if tenant_id is not None:
        q = q.filter(models.Medicine.tenant_id == tenant_id)
    if _supports_for_update(db):
        q = q.with_for_update()
    return q.first()


def _add_ledger_entry(db: Session, medicine: models.Medicine, change_qty: Decimal,
                       reason: str, bill_item_id: Optional[int] = None,
                       sale_id: Optional[int] = None, note: Optional[str] = None,
                       created_by_user_id: Optional[int] = None) -> models.StockLedger:
    """
    Core stock ledger write — single path for all stock changes.

    Priority 1: After writing the ledger entry, checks whether this change
    caused the medicine to cross below its low_stock_threshold. If it did,
    fires LowStockCrossedEvent via the event bus. The event subscriber
    (handle_low_stock_crossed in subscribers.py) writes the Notification row.

    The crossing check is: old_balance >= threshold AND new_balance < threshold.
    This fires only on the crossing, not on every sale while already below
    threshold (which would spam an alert for every single tablet sold).
    """
    old_balance = _to_decimal(medicine.current_stock)
    new_balance = old_balance + change_qty
    medicine.current_stock = new_balance
    entry = models.StockLedger(
        tenant_id=medicine.tenant_id, medicine_id=medicine.id, change_qty=change_qty, resulting_balance=new_balance,
        reason=reason, reference_bill_item_id=bill_item_id, reference_sale_id=sale_id,
        note=note, created_by_user_id=created_by_user_id,
    )
    db.add(entry)
    db.flush()   # assigns entry.id, needed by callers that reference it (e.g. TrustChain audit logging)

    # --- Priority 1: Low-stock crossing detection ---
    threshold = medicine.low_stock_threshold
    if threshold is not None:
        threshold_d = _to_decimal(threshold)
        crossed_below = old_balance >= threshold_d and new_balance < threshold_d
        if crossed_below:
            try:
                from app.events.bus import event_bus
                from app.events.events import LowStockCrossedEvent
                event_bus.publish(LowStockCrossedEvent(
                    medicine_id=medicine.id,
                    medicine_name=medicine.particulars,
                    old_balance=float(old_balance),
                    new_balance=float(new_balance),
                    threshold=float(threshold_d),
                    db=db,
                ))
            except Exception as exc:
                # Never crash the core stock write because of a notification failure.
                # Log and continue — the ledger entry is always written regardless.
                from app.core.logging import get_logger
                get_logger("stock_service").warning(
                    f"LowStockCrossedEvent publish failed for medicine #{medicine.id}: {exc}"
                )

    return entry


def add_stock_from_confirmed_bill_item(db: Session, bill_item: models.BillItem) -> None:
    if not bill_item.medicine_id:
        return
    medicine = _get_medicine_for_update(db, bill_item.tenant_id, bill_item.medicine_id)
    if not medicine:
        return
    # Defensive: never allow a cross-tenant bill item to mutate another tenant's stock.
    if bill_item.tenant_id is not None and medicine.tenant_id != bill_item.tenant_id:
        raise ConflictError("Bill item and medicine tenant mismatch")
    received = _to_decimal(bill_item.qty) + _to_decimal(bill_item.free_qty)
    if received <= 0:
        return
    _add_ledger_entry(
        db, medicine, received, reason="bill_received",
        bill_item_id=bill_item.id,
        note=f"Received via bill #{bill_item.bill_id}",
    )


def get_last_purchase_info(db: Session, medicine_id: int) -> Optional[dict]:
    item = (
        db.query(models.BillItem)
        .join(models.Bill, models.BillItem.bill_id == models.Bill.id)
        .filter(models.BillItem.medicine_id == medicine_id, models.Bill.status == "confirmed")
        .order_by(desc(models.Bill.invoice_date), desc(models.Bill.uploaded_at))
        .first()
    )
    if not item:
        return None
    bill = item.bill
    return {
        "distributor_id": bill.distributor_id,
        "distributor_name": bill.distributor.name if bill.distributor else None,
        "qty_received": float(item.qty or 0),
        "free_qty_received": float(item.free_qty or 0),
        "rate": float(item.computed_cost_per_unit) if item.computed_cost_per_unit is not None else None,
        "mrp": float(item.mrp) if item.mrp is not None else None,
        "purchase_date": bill.invoice_date or bill.uploaded_at,
    }


def get_stock_snapshot(db: Session, tenant_id: int, medicine_id: int) -> Optional[dict]:
    medicine = db.query(models.Medicine).filter_by(id=medicine_id, tenant_id=tenant_id).first()
    if not medicine:
        return None
    return {
        "medicine_id": medicine.id,
        "medicine_name": medicine.particulars,
        "current_stock": float(medicine.current_stock or 0),
        "low_stock_threshold": float(medicine.low_stock_threshold) if medicine.low_stock_threshold is not None else None,
        "last_purchase": get_last_purchase_info(db, medicine_id),
    }


def _run_sale_surveillance(db: Session, tenant_id: int, medicine_id: int, qty_sold: Decimal) -> None:
    # Best-effort side signal; never fail the sale because surveillance cannot run.
    try:
        # record_sale_signal flushes; it participates in the current transaction if
        # called before commit, or will require a follow-up commit if called after.
        surveillance_service.record_sale_signal(
            db, medicine_id, int(qty_sold.to_integral_value(rounding="ROUND_HALF_UP")),
            tenant_id=tenant_id,
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Surveillance hook failed: {e}")


def record_sale(db: Session, tenant_id: int, medicine_id: int, qty_sold: float, customer_id: Optional[int] = None,
                 created_by_user_id: Optional[int] = None, commit: bool = True) -> dict:
    """
    Record a single sale. Raises domain errors for missing medicine or
    insufficient stock. When commit=True (default), commits the transaction and
    runs best-effort surveillance; when False, caller owns the transaction.

    Concurrency: locks the medicine row (when supported) and rechecks stock
    inside the transaction to prevent negative inventory under races.
    """
    qty_d = _to_decimal(qty_sold)
    if qty_d <= 0:
        raise ValidationError("Quantity sold must be greater than 0")

    medicine = _get_medicine_for_update(db, tenant_id, medicine_id)
    if not medicine:
        raise NotFoundError("Medicine not found")

    current = _to_decimal(medicine.current_stock)
    if qty_d > current:
        raise ConflictError("Insufficient stock")

    sale = models.Sale(
        tenant_id=tenant_id, medicine_id=medicine_id, qty_sold=qty_d,
        sold_at=datetime.now(timezone.utc), customer_id=customer_id,
    )
    db.add(sale)
    db.flush()

    _add_ledger_entry(
        db, medicine, -qty_d, reason="sale",
        sale_id=sale.id, note=f"Sold {float(qty_d)} units", created_by_user_id=created_by_user_id,
    )

    if commit:
        db.commit()
        _run_sale_surveillance(db, tenant_id, medicine_id, qty_d)
        db.commit()
        db.refresh(sale)
    else:
        _run_sale_surveillance(db, tenant_id, medicine_id, qty_d)

    snapshot = get_stock_snapshot(db, tenant_id, medicine_id)
    snapshot["sale_id"] = sale.id
    return snapshot


def get_reorder_list(db: Session, tenant_id: int) -> list[dict]:
    groups: dict[str, dict] = {}

    def _get_group(distributor_id: Optional[int], distributor_name: str) -> dict:
        key = distributor_name
        if key not in groups:
            groups[key] = {"distributor_id": distributor_id, "distributor_name": distributor_name, "items": []}
        return groups[key]

    low_stock_medicines = (
        db.query(models.Medicine)
        .filter(models.Medicine.tenant_id == tenant_id)
        .filter(models.Medicine.low_stock_threshold.isnot(None))
        .filter(models.Medicine.current_stock < models.Medicine.low_stock_threshold)
        .all()
    )
    for medicine in low_stock_medicines:
        last = get_last_purchase_info(db, medicine.id)
        distributor_name = last["distributor_name"] if last and last["distributor_name"] else "Unknown distributor — check manually"
        distributor_id = last["distributor_id"] if last else None
        group = _get_group(distributor_id, distributor_name)
        group["items"].append({
            "id": None,
            "medicine_id": medicine.id,
            "name": medicine.particulars,
            "current_stock": float(medicine.current_stock or 0),
            "low_stock_threshold": float(medicine.low_stock_threshold),
            "last_qty_received": last["qty_received"] if last else None,
            "last_rate": last["rate"] if last else None,
            "last_purchase_date": last["purchase_date"] if last else None,
            "quantity_needed": None,
            "note": None,
            "source": "auto_low_stock",
        })

    manual_items = db.query(models.ReorderItem).filter(models.ReorderItem.tenant_id == tenant_id, models.ReorderItem.fulfilled.is_(False)).all()
    for ri in manual_items:
        if ri.distributor_id:
            distributor_name = ri.distributor.name
        else:
            distributor_name = "Unassigned — pick a distributor"
        group = _get_group(ri.distributor_id, distributor_name)

        name = ri.medicine.particulars if ri.medicine else (ri.custom_name or "Unnamed item")
        last = get_last_purchase_info(db, ri.medicine_id) if ri.medicine_id else None
        group["items"].append({
            "id": ri.id,
            "medicine_id": ri.medicine_id,
            "name": name,
            "current_stock": float(ri.medicine.current_stock or 0) if ri.medicine else None,
            "low_stock_threshold": float(ri.medicine.low_stock_threshold) if ri.medicine and ri.medicine.low_stock_threshold is not None else None,
            "last_qty_received": last["qty_received"] if last else None,
            "last_rate": last["rate"] if last else None,
            "last_purchase_date": last["purchase_date"] if last else None,
            "quantity_needed": float(ri.quantity_needed) if ri.quantity_needed is not None else None,
            "note": ri.note,
            "source": "manual",
        })

    def _sort_key(group):
        is_fallback_bucket = "Unknown" in group["distributor_name"] or "Unassigned" in group["distributor_name"]
        return (is_fallback_bucket, group["distributor_name"])

    return sorted(groups.values(), key=_sort_key)


def add_manual_reorder_item(
    db: Session,
    medicine_id: Optional[int],
    custom_name: Optional[str],
    distributor_id: Optional[int],
    distributor_name_new: Optional[str],
    quantity_needed: Optional[float],
    note: Optional[str],
    tenant_id: Optional[int] = None,
) -> models.ReorderItem:
    if distributor_name_new and not distributor_id:
        normalized_name = distributor_name_new.strip().upper()
        existing = db.query(models.Distributor).filter_by(name=normalized_name, tenant_id=tenant_id).first()
        if existing:
            distributor_id = existing.id
        else:
            try:
                with db.begin_nested():
                    new_distributor = models.Distributor(name=normalized_name, tenant_id=tenant_id)
                    db.add(new_distributor)
                    db.flush()
                    distributor_id = new_distributor.id
            except IntegrityError:
                existing = db.query(models.Distributor).filter_by(name=normalized_name, tenant_id=tenant_id).first()
                if not existing:
                    raise
                distributor_id = existing.id

    item = models.ReorderItem(
        medicine_id=medicine_id, custom_name=custom_name, distributor_id=distributor_id,
        tenant_id=tenant_id,
        quantity_needed=quantity_needed, note=note, source="manual", fulfilled=False,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def mark_reorder_item_fulfilled(db: Session, reorder_item_id: int) -> bool:
    item = db.get(models.ReorderItem, reorder_item_id)
    if not item:
        return False
    item.fulfilled = True
    db.commit()
    return True

def delete_reorder_item(db: Session, reorder_item_id: int) -> bool:
    item = db.get(models.ReorderItem, reorder_item_id)
    if not item:
        return False
    db.delete(item)
    db.commit()
    return True


def record_adjustment(db: Session, medicine_id: int, new_total_stock: float, note: Optional[str] = None,
                       created_by_user_id: Optional[int] = None, tenant_id: Optional[int] = None) -> dict:
    medicine = _get_medicine_for_update(db, tenant_id, medicine_id)
    if not medicine:
        raise NotFoundError("Medicine not found")
    current = _to_decimal(medicine.current_stock)
    target = _to_decimal(new_total_stock)
    if target < 0:
        raise ValidationError("Stock cannot be negative")
    diff = target - current
    ledger_entry = _add_ledger_entry(
        db, medicine, diff, reason="manual_adjustment",
        note=note or "Manual inventory adjustment", created_by_user_id=created_by_user_id,
    )

    # --- TrustChain (Pillar 4) ---
    performer = db.get(models.User, created_by_user_id) if created_by_user_id else None
    audit_service.log_event(db, "stock_adjustment", ledger_entry.id, {
        "medicine_id": medicine.id,
        "medicine_name": medicine.particulars,
        "previous_stock": float(current),
        "new_stock": float(target),
        "change_qty": float(diff),
        "note": note,
        "performed_by_user_id": created_by_user_id,
        "performed_by_username": performer.username if performer else None,
    })

    db.commit()
    return {
        "medicine_id": medicine.id,
        "medicine_name": medicine.particulars,
        "change_qty": float(diff),
        "resulting_balance": float(target),
    }


def get_stock_ledger(db: Session, tenant_id: int, limit: int = 50, offset: int = 0) -> list[dict]:
    """
    Priority 2b: offset added for pagination. limit preserved for backward compat.
    """
    rows = (
        db.query(models.StockLedger)
        .filter(models.StockLedger.tenant_id == tenant_id)
        .order_by(desc(models.StockLedger.created_at))
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "medicine_id": r.medicine_id,
            "medicine_name": r.medicine.particulars if r.medicine else None,
            "change_qty": float(r.change_qty),
            "resulting_balance": float(r.resulting_balance),
            "reason": r.reason.value if hasattr(r.reason, "value") else str(r.reason),
            "note": r.note,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


def get_stock_ledger_count(db: Session, tenant_id: int) -> int:
    """Total row count for pagination metadata."""
    return db.query(models.StockLedger).filter(models.StockLedger.tenant_id == tenant_id).count()
