"""
Customer Health Companion endpoints (Pillar 5, Part A): profile lookup/
creation, the credit/udhaar ledger, and adherence (overdue refill) alerts.
Available to any logged-in user - staff handle credit and adherence
follow-ups day-to-day, not just the Owner, matching this codebase's
existing convention of reserving require_owner for financial REPORTS
(GST, Analytics) rather than routine operational actions.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas
from app.services import customer_service
from app.deps import get_current_user

router = APIRouter(prefix="/customers", dependencies=[Depends(get_current_user)], tags=["customers"])


def _summary_or_404(db: Session, customer_id: int) -> schemas.CustomerOut:
    summary = customer_service.get_customer_summary(db, customer_id)
    if not summary:
        raise HTTPException(404, "Customer not found")
    return schemas.CustomerOut(**summary)


@router.get("", response_model=list[schemas.CustomerOut])
def search_customers(q: Optional[str] = Query(None), db: Session = Depends(get_db)):
    customers = customer_service.search_customers(db, q=q)
    return [_summary_or_404(db, c.id) for c in customers]


@router.post("", response_model=schemas.CustomerOut)
def create_or_get_customer(payload: schemas.CustomerCreate, db: Session = Depends(get_db)):
    """
    Idempotent by phone number - calling this with a phone that already
    exists just returns/updates that customer rather than erroring, since
    the natural flow is "look this phone number up, create it if it's
    genuinely new" in one step at the point of sale.
    """
    customer = customer_service.get_or_create_customer(
        db, phone=payload.phone, name=payload.name, consented=payload.consent_given
    )
    db.commit()
    return _summary_or_404(db, customer.id)


@router.get("/outstanding", response_model=list[schemas.OutstandingBalanceItem])
def outstanding_balances(db: Session = Depends(get_db)):
    """The 'who owes us money' screen - highest balance first."""
    return customer_service.list_customers_with_outstanding_balance(db)


@router.get("/adherence-alerts", response_model=list[schemas.AdherenceAlertOut])
def adherence_alerts(db: Session = Depends(get_db)):
    """Every consented customer whose usual refill gap has been exceeded, worst-overdue first."""
    return customer_service.compute_adherence_alerts(db)


@router.get("/{customer_id}", response_model=schemas.CustomerOut)
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    return _summary_or_404(db, customer_id)


@router.get("/{customer_id}/ledger", response_model=list[schemas.CustomerCreditEntryOut])
def get_ledger(customer_id: int, db: Session = Depends(get_db)):
    return customer_service.get_credit_ledger(db, customer_id)


@router.post("/{customer_id}/credit/charge", response_model=schemas.CustomerOut)
def charge_credit(customer_id: int, payload: schemas.CreditChargeRequest, db: Session = Depends(get_db)):
    try:
        customer_service.charge_credit(db, customer_id, payload.amount, note=payload.note)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _summary_or_404(db, customer_id)


@router.post("/{customer_id}/credit/payment", response_model=schemas.CustomerOut)
def record_payment(customer_id: int, payload: schemas.CreditPaymentRequest, db: Session = Depends(get_db)):
    try:
        customer_service.record_payment(db, customer_id, payload.amount, note=payload.note)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _summary_or_404(db, customer_id)