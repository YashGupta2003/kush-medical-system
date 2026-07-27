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


def create_batch_from_confirmed_item(db: Session, bill_item: models.BillItem) -> None:
    """
    Called once per matched line item when a bill is confirmed (see
    routers/bills.py confirm_bill). Always creates a batch row - even when
    the expiry couldn't be parsed - so the quantity/batch-number is on
    record and the item shows up in "missing expiry info" for the user to
    complete, rather than silently having no batch tracking at all.
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

    db.add(models.MedicineBatch(
        medicine_id=bill_item.medicine_id,
        batch_no=bill_item.batch,
        expiry_date=parsed_date,
        qty_received=qty,
        bill_item_id=bill_item.id,
        distributor_id=bill.distributor_id if bill else None,
    ))
    # Flush immediately (not just commit) so the bill_item_id uniqueness
    # guard above actually sees this row if the function is somehow called
    # again for the same item before the enclosing transaction commits -
    # otherwise two calls in the same transaction could both pass the
    # "does it already exist" check and only collide at commit time.
    db.flush()


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
    all_dated = (
        db.query(models.MedicineBatch)
        .filter(models.MedicineBatch.expiry_date.isnot(None))
        .all()
    )
    expired = critical = warning = 0
    for b in all_dated:
        d = (b.expiry_date - today).days
        if d < 0:
            expired += 1
        elif d <= 7:
            critical += 1
        elif d <= 30:
            warning += 1

    missing_count = (
        db.query(models.MedicineBatch)
        .filter(models.MedicineBatch.expiry_date.is_(None))
        .count()
    )
    return {"expired": expired, "critical": critical, "warning": warning, "missing_expiry": missing_count}


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
    batch = db.query(models.MedicineBatch).get(batch_id)
    if not batch:
        return False
    batch.expiry_date = expiry_date
    db.commit()
    return True