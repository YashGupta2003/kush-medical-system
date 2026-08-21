"""
Everything to do with medicine batch expiry tracking:
  - creating a batch record whenever a bill is confirmed
  - the "expiring soon" dashboard, bucketed by urgency
  - finding bills where expiry couldn't be read, so the user can be
    prompted to fill it in by hand
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import asc

from app import models
from app.services.expiry_parser import parse_expiry_string
from app.services import audit_service


def create_batch_from_confirmed_item(db: Session, bill_item: models.BillItem) -> None:
    """
    Called once per matched line item when a bill is confirmed (see
    routers/bills.py confirm_bill). Always creates a batch row - even when
    the expiry couldn't be parsed - so the quantity/batch-number is on
    record and the item shows up in "missing expiry info" for the user to
    complete, rather than silently having no batch tracking at all.

    Also appends a tamper-evident 'batch_received' entry to TrustChain's
    ledger (Pillar 4) - a batch's received quantity is exactly the kind of
    number a GST audit cares couldn't have been quietly altered after
    receiving.
    """
    if not bill_item.medicine_id:
        return
    # Guard against creating a duplicate batch if this bill item was
    # somehow processed twice (bill_item_id is unique on medicine_batches).
    existing = db.query(models.MedicineBatch).filter_by(bill_item_id=bill_item.id).first()
    if existing:
        return

    parsed_date = parse_expiry_string(bill_item.exp_date)
    qty = Decimal(str(bill_item.qty or 0)) + Decimal(str(bill_item.free_qty or 0))
    bill = bill_item.bill

    batch = models.MedicineBatch(
        medicine_id=bill_item.medicine_id,
        batch_no=bill_item.batch,
        expiry_date=parsed_date,
        qty_received=qty,
        bill_item_id=bill_item.id,
        distributor_id=bill.distributor_id if bill else None,
    )
    db.add(batch)
    # Flush immediately (not just commit) so the bill_item_id uniqueness
    # guard above actually sees this row if the function is somehow called
    # again for the same item before the enclosing transaction commits -
    # otherwise two calls in the same transaction could both pass the
    # "does it already exist" check and only collide at commit time. This
    # flush also assigns batch.id, needed below as the audit entry's
    # reference_id.
    db.flush()

    # --- TrustChain (Pillar 4) ---
    audit_service.log_event(db, "batch_received", batch.id, {
        "medicine_id": bill_item.medicine_id,
        "batch_no": batch.batch_no,
        "expiry_date": parsed_date.isoformat() if parsed_date else None,
        "qty_received": float(qty),
        "bill_item_id": bill_item.id,
        "distributor_id": batch.distributor_id,
    })


def _urgency_for(days_remaining: int) -> str:
    if days_remaining < 0:
        return "expired"
    if days_remaining <= 7:
        return "critical"
    if days_remaining <= 30:
        return "warning"
    return "upcoming"


def get_expiry_dashboard(db: Session, days: int = 90) -> list[dict]:
    """
    Returns every batch expiring within `days` from today (including
    already-expired ones), sorted soonest-first, each tagged with an
    urgency bucket the frontend uses for color-coding:
      expired   - already past expiry, pull from shelf now
      critical  - expiring within 7 days
      warning   - expiring within 30 days
      upcoming  - expiring within the requested window but beyond 30 days
    """
    today = date.today()
    horizon = today + timedelta(days=days)

    batches = (
        db.query(models.MedicineBatch)
        .filter(models.MedicineBatch.expiry_date.isnot(None))
        .filter(models.MedicineBatch.expiry_date <= horizon)
        .order_by(asc(models.MedicineBatch.expiry_date))
        .all()
    )

    result = []
    for b in batches:
        days_remaining = (b.expiry_date - today).days
        result.append({
            "batch_id": b.id,
            "medicine_id": b.medicine_id,
            "medicine_name": b.medicine.particulars if b.medicine else "Unknown",
            "batch_no": b.batch_no,
            "expiry_date": b.expiry_date,
            "days_remaining": days_remaining,
            "urgency": _urgency_for(days_remaining),
            "qty_received": float(b.qty_received or 0),
            "distributor_name": b.distributor.name if b.distributor else None,
        })
    return result


def get_expiry_summary(db: Session) -> dict:
    """Small counts used for the nav-bar badge and dashboard stat cards."""
    today = date.today()

    # BUG FIX: Previous code loaded all batch rows into Python memory and counted
    # buckets in a loop. For large inventories this is O(N) RAM. Use SQL
    # conditional aggregates (CASE WHEN) to count in the database instead.
    from sqlalchemy import case, func

    expired_count, critical_count, warning_count = (
        db.query(
            func.sum(case((models.MedicineBatch.expiry_date < today, 1), else_=0)),
            func.sum(case(
                (models.MedicineBatch.expiry_date >= today,
                 case((models.MedicineBatch.expiry_date <= today + timedelta(days=7), 1), else_=0)),
                else_=0
            )),
            func.sum(case(
                (models.MedicineBatch.expiry_date > today + timedelta(days=7),
                 case((models.MedicineBatch.expiry_date <= today + timedelta(days=30), 1), else_=0)),
                else_=0
            )),
        )
        .filter(models.MedicineBatch.expiry_date.isnot(None))
        .one()
    )

    missing_count = (
        db.query(models.MedicineBatch)
        .filter(models.MedicineBatch.expiry_date.is_(None))
        .count()
    )
    return {
        "expired": int(expired_count or 0),
        "critical": int(critical_count or 0),
        "warning": int(warning_count or 0),
        "missing_expiry": missing_count,
    }


def get_missing_expiry_batches(db: Session) -> list[dict]:
    """
    Batches that exist (so quantity/batch-number is on record) but whose
    expiry couldn't be read from the bill photo - these need the user to
    type the date in by hand. This is what powers the 'please add expiry
    date' prompt.
    """
    batches = (
        db.query(models.MedicineBatch)
        .filter(models.MedicineBatch.expiry_date.is_(None))
        .order_by(models.MedicineBatch.created_at.desc())
        .all()
    )
    result = []
    for b in batches:
        result.append({
            "batch_id": b.id,
            "medicine_id": b.medicine_id,
            "medicine_name": b.medicine.particulars if b.medicine else "Unknown",
            "batch_no": b.batch_no,
            "qty_received": float(b.qty_received or 0),
            "distributor_name": b.distributor.name if b.distributor else None,
        })
    return result


def fill_missing_expiry(db: Session, batch_id: int, expiry_date: date) -> bool:
    batch = db.get(models.MedicineBatch, batch_id)
    if not batch:
        return False
    batch.expiry_date = expiry_date
    db.commit()
    return True