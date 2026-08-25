"""
Pillar 5, Part A — Customer Profiles, Credit/Udhaar Ledger & Adherence Tracking.

A single new Customer model (identified by phone number - the natural ID
a small shop already uses) powers three features:

  1. Credit/Udhaar ledger - charge_credit() / record_payment() below,
     mirroring stock_service.py's StockLedger running-balance pattern
     exactly (every change is one immutable row, the balance is the last
     row's resulting_balance - same design, just for money owed instead
     of units on hand). Every charge/payment is ALSO logged to TrustChain
     (Pillar 4) via audit_service.log_event - an udhaar balance is
     precisely the kind of number a later dispute needs to be provably
     unaltered.
  2. Purchase history & adherence tracking - compute_adherence_alerts()
     reuses the Sale table Stock & Reorder already writes to (now with an
     optional customer_id - see stock_service.record_sale), so no new
     sales-tracking infrastructure is needed, only a read-side
     aggregation.
  3. Symptom-to-stock bot - lives in symptom_bot_service.py, but reads
     this same Customer model for identity/consent.

Consent: consent_given_at gates adherence tracking specifically (using a
customer's purchase PATTERN in a health-relevant way needs explicit
opt-in), but NOT the credit ledger (a debt is a factual record either
party can already reference regardless of consent to health tracking) -
these are deliberately kept as separate concerns, not one blanket flag.
"""
from datetime import datetime, timezone
from decimal import Decimal
from statistics import mean
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import desc, or_

from app import models
from app.services import audit_service

# Adherence heuristic thresholds - see compute_adherence_alerts()'s
# docstring for the reasoning behind each one.
MIN_PURCHASES_FOR_PATTERN = 2
MIN_AVG_GAP_DAYS = 10      # below this, purchases are too frequent to be a "refill cycle"
MAX_AVG_GAP_DAYS = 120     # above this, too infrequent to confidently call it a recurring pattern
OVERDUE_MULTIPLIER = 1.5   # flag once the gap since last purchase exceeds 1.5x the customer's own historical average


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------
def get_or_create_customer(db: Session, phone: str, name: Optional[str] = None, consented: bool = False) -> models.Customer:
    phone = phone.strip()
    customer = db.query(models.Customer).filter_by(phone=phone).first()
    if customer:
        if name and not customer.name:
            customer.name = name
        if consented and not customer.consent_given_at:
            customer.consent_given_at = datetime.now(timezone.utc)
        db.flush()
        return customer

    customer = models.Customer(
        phone=phone, name=name,
        consent_given_at=datetime.now(timezone.utc) if consented else None,
    )
    db.add(customer)
    db.flush()
    return customer


def search_customers(db: Session, q: Optional[str] = None, limit: int = 20) -> list[models.Customer]:
    query = db.query(models.Customer)
    if q:
        q = q.strip()
        query = query.filter(or_(models.Customer.phone.ilike(f"%{q}%"), models.Customer.name.ilike(f"%{q}%")))
    return query.order_by(models.Customer.name).limit(limit).all()


def get_customer_summary(db: Session, customer_id: int) -> Optional[dict]:
    customer = db.get(models.Customer, customer_id)
    if not customer:
        return None

    last_sale = (
        db.query(models.Sale)
        .filter_by(customer_id=customer_id)
        .order_by(desc(models.Sale.sold_at))
        .first()
    )
    total_purchases = db.query(models.Sale).filter_by(customer_id=customer_id).count()

    return {
        "customer_id": customer.id,
        "phone": customer.phone,
        "name": customer.name,
        "consent_given_at": customer.consent_given_at,
        "current_balance": float(get_customer_balance(db, customer_id)),
        "total_purchases": total_purchases,
        "last_visit": last_sale.sold_at if last_sale else None,
    }


# ---------------------------------------------------------------------------
# Credit / udhaar ledger
# ---------------------------------------------------------------------------
def get_customer_balance(db: Session, customer_id: int) -> Decimal:
    last = (
        db.query(models.CustomerCredit)
        .filter_by(customer_id=customer_id)
        .order_by(models.CustomerCredit.id.desc())
        .first()
    )
    return last.resulting_balance if last else Decimal("0")


def _add_credit_entry(db: Session, customer: models.Customer, change_amount: Decimal,
                       reason: str, reference_sale_id: Optional[int] = None,
                       note: Optional[str] = None) -> models.CustomerCredit:
    current = get_customer_balance(db, customer.id)
    new_balance = current + change_amount
    entry = models.CustomerCredit(
        customer_id=customer.id, change_amount=change_amount, resulting_balance=new_balance,
        reason=reason, reference_sale_id=reference_sale_id, note=note,
    )
    db.add(entry)
    db.flush()
    return entry


def charge_credit(db: Session, customer_id: int, amount: float, note: Optional[str] = None,
                   reference_sale_id: Optional[int] = None) -> dict:
    """Records a sale given "on credit" (udhaar) - increases what this customer owes."""
    if amount <= 0:
        raise ValueError("Credit amount must be greater than 0")
    customer = db.get(models.Customer, customer_id)
    if not customer:
        raise ValueError("Customer not found")

    entry = _add_credit_entry(db, customer, Decimal(str(amount)), "credit_sale", reference_sale_id, note)

    # --- TrustChain (Pillar 4) ---
    audit_service.log_event(db, "credit_charge", entry.id, {
        "customer_id": customer.id, "customer_phone": customer.phone, "customer_name": customer.name,
        "amount": float(amount), "new_balance": float(entry.resulting_balance), "note": note,
    })

    db.commit()
    return {"customer_id": customer.id, "change_amount": float(amount), "resulting_balance": float(entry.resulting_balance)}


def record_payment(db: Session, customer_id: int, amount: float, note: Optional[str] = None) -> dict:
    """Records a payment against an outstanding udhaar balance."""
    if amount <= 0:
        raise ValueError("Payment amount must be greater than 0")
    customer = db.get(models.Customer, customer_id)
    if not customer:
        raise ValueError("Customer not found")

    entry = _add_credit_entry(db, customer, -Decimal(str(amount)), "payment_received", None, note)

    # --- TrustChain (Pillar 4) ---
    audit_service.log_event(db, "credit_payment", entry.id, {
        "customer_id": customer.id, "customer_phone": customer.phone, "customer_name": customer.name,
        "amount": float(amount), "new_balance": float(entry.resulting_balance), "note": note,
    })

    db.commit()
    return {"customer_id": customer.id, "change_amount": float(-amount), "resulting_balance": float(entry.resulting_balance)}


def get_credit_ledger(db: Session, customer_id: int, limit: int = 50) -> list[models.CustomerCredit]:
    return (
        db.query(models.CustomerCredit)
        .filter_by(customer_id=customer_id)
        .order_by(desc(models.CustomerCredit.created_at))
        .limit(limit)
        .all()
    )


def list_customers_with_outstanding_balance(db: Session, limit: int = 100) -> list[dict]:
    """The 'who owes us money' screen - sorted highest balance first."""
    # BUG FIX: previous code ran one query per customer (N+1).
    # Now: a single query fetches the latest CustomerCredit row per customer
    # using a correlated subquery, then filters for positive balances.
    from sqlalchemy import func
    from sqlalchemy.orm import aliased

    # Subquery: max(id) per customer_id (the most recent ledger row)
    latest_id_sub = (
        db.query(func.max(models.CustomerCredit.id))
        .filter(models.CustomerCredit.customer_id == models.Customer.id)
        .correlate(models.Customer)
        .scalar_subquery()
    )

    rows = (
        db.query(
            models.Customer.id,
            models.Customer.phone,
            models.Customer.name,
            models.CustomerCredit.resulting_balance,
        )
        .join(models.CustomerCredit, models.CustomerCredit.id == latest_id_sub)
        .filter(models.CustomerCredit.resulting_balance > 0)
        .order_by(models.CustomerCredit.resulting_balance.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "customer_id": r[0],
            "phone": r[1],
            "name": r[2],
            "current_balance": float(r[3]),
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Adherence tracking
# ---------------------------------------------------------------------------
def compute_adherence_alerts(db: Session, customer_id: Optional[int] = None) -> list[dict]:
    """
    Data-driven refill-overdue detection - deliberately does NOT depend on
    a curated "these are chronic-disease medicines" list (which would need
    ongoing maintenance and would miss anything not on it). Instead: ANY
    (customer, medicine) pair with a REGULAR repeat-purchase pattern is
    itself the signal that this is a refill relationship - a customer
    buying the same BP tablet every ~28 days IS demonstrating a refill
    cycle regardless of whether that medicine happens to be tagged
    "chronic" anywhere in the system.

    Algorithm, per (customer, medicine) pair with 2+ purchases:
      avg_gap_days = mean of the gaps between consecutive purchase dates.
      Only treated as a genuine refill pattern if MIN_AVG_GAP_DAYS <=
      avg_gap_days <= MAX_AVG_GAP_DAYS - this filters out same-week
      re-buys (not a "cycle") and one-off coincidental repeats months or
      years apart (not reliably predictable).
      Flagged OVERDUE once days-since-last-purchase exceeds
      avg_gap_days * OVERDUE_MULTIPLIER.

    Only sales linked to a customer WITH consent_given_at set are
    considered - adherence tracking uses purchase-pattern data in a
    health-relevant way, so it requires the customer's explicit opt-in
    (unlike the credit ledger, which any customer can be tracked in).
    """
    query = (
        db.query(models.Sale)
        .join(models.Customer, models.Sale.customer_id == models.Customer.id)
        .filter(models.Customer.consent_given_at.isnot(None))
    )
    if customer_id is not None:
        query = query.filter(models.Sale.customer_id == customer_id)

    sales = query.order_by(models.Sale.sold_at.asc()).all()

    groups: dict[tuple, list] = {}
    for s in sales:
        if not s.customer_id or not s.medicine_id:
            continue
        groups.setdefault((s.customer_id, s.medicine_id), []).append(s.sold_at)

    today = datetime.now(timezone.utc)
    alerts = []

    for (cust_id, med_id), dates in groups.items():
        if len(dates) < MIN_PURCHASES_FOR_PATTERN:
            continue
        dates = sorted(dates)
        gaps = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
        avg_gap = mean(gaps)
        if not (MIN_AVG_GAP_DAYS <= avg_gap <= MAX_AVG_GAP_DAYS):
            continue

        last_purchase = dates[-1]
        if last_purchase.tzinfo is None:
            last_purchase = last_purchase.replace(tzinfo=timezone.utc)
        days_since = (today - last_purchase).days
        if days_since <= avg_gap * OVERDUE_MULTIPLIER:
            continue

        customer = db.get(models.Customer, cust_id)
        medicine = db.get(models.Medicine, med_id)
        if not customer or not medicine:
            continue

        alerts.append({
            "customer_id": cust_id,
            "customer_name": customer.name,
            "customer_phone": customer.phone,
            "medicine_id": med_id,
            "medicine_name": medicine.particulars,
            "avg_gap_days": round(avg_gap, 1),
            "days_since_last_purchase": days_since,
            "days_overdue": round(days_since - avg_gap, 1),
            "last_purchase_date": last_purchase,
            "purchase_count": len(dates),
        })

    alerts.sort(key=lambda a: -a["days_overdue"])
    return alerts