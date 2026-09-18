"""
Customer Health Companion endpoints (Pillar 5, Part A): profile lookup/
creation, the credit/udhaar ledger, and adherence (overdue refill) alerts.
Available to any logged-in user - staff handle credit and adherence
follow-ups day-to-day, not just the Owner, matching this codebase's
existing convention of reserving require_owner for financial REPORTS
(GST, Analytics) rather than routine operational actions.

Task 2: search_customers and get_ledger are now paginated using the same
{items, total, page, page_size} shape as medicines.py's list endpoint.
Page size is capped at 100 server-side regardless of client request.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas, models
from app.services import customer_service
from app.deps import get_current_user

router = APIRouter(prefix="/customers", dependencies=[Depends(get_current_user)], tags=["customers"])

# Maximum page_size the client may request — hard cap enforced server-side.
_MAX_PAGE_SIZE = 100


def _summary_or_404(db: Session, customer_id: int, current_user: models.User) -> schemas.CustomerOut:
    summary = customer_service.get_customer_summary(db, customer_id, tenant_id=current_user.tenant_id)
    if not summary:
        raise HTTPException(404, "Customer not found")
    return schemas.CustomerOut(**summary)


@router.get("", response_model=schemas.PaginatedResponse[schemas.CustomerOut])
def search_customers(
    q: Optional[str] = Query(None, description="Search by phone or name"),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(20, ge=1, le=_MAX_PAGE_SIZE, description="Items per page (max 100)"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Search or list customers with pagination.
    Returns {items, total, page, page_size} — same shape as /medicines.
    """
    # Cap page_size defensively even though Query already enforces le=100
    page_size = min(page_size, _MAX_PAGE_SIZE)

    query = (
        db.query(
            models.Customer,
            func.max(models.Sale.sold_at).label("last_visit"),
            func.count(models.Sale.id).label("total_purchases"),
        )
        .outerjoin(models.Sale, models.Sale.customer_id == models.Customer.id)
        .filter(models.Customer.tenant_id == current_user.tenant_id)
    )

    if q:
        query = query.filter(
            or_(
                models.Customer.phone.ilike(f"%{q}%"),
                models.Customer.name.ilike(f"%{q}%"),
            )
        )

    grouped = query.group_by(models.Customer.id)
    total = grouped.count()

    rows = (
        grouped.order_by(models.Customer.name)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    summaries = []
    for c, last_visit, total_purchases in rows:
        summaries.append(
            schemas.CustomerOut(
                customer_id=c.id,
                name=c.name,
                phone=c.phone,
                current_balance=float(customer_service.get_customer_balance(db, c.id)),
                last_visit=last_visit,
                total_purchases=total_purchases,
            )
        )

    return schemas.PaginatedResponse(
        items=summaries,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=schemas.CustomerOut)
def create_or_get_customer(payload: schemas.CustomerCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """
    Idempotent by phone number - calling this with a phone that already
    exists just returns/updates that customer rather than erroring, since
    the natural flow is "look this phone number up, create it if it's
    genuinely new" in one step at the point of sale.
    """
    customer = customer_service.get_or_create_customer(
        db, phone=payload.phone, tenant_id=current_user.tenant_id, name=payload.name, consented=payload.consent_given
    )
    db.commit()
    return _summary_or_404(db, customer.id, current_user)


@router.get("/outstanding", response_model=list[schemas.OutstandingBalanceItem])
def outstanding_balances(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """The 'who owes us money' screen - highest balance first."""
    return customer_service.list_customers_with_outstanding_balance(db, tenant_id=current_user.tenant_id)


@router.get("/adherence-alerts", response_model=list[schemas.AdherenceAlertOut])
def adherence_alerts(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Every consented customer whose usual refill gap has been exceeded, worst-overdue first."""
    return customer_service.compute_adherence_alerts(db, tenant_id=current_user.tenant_id)


@router.get("/{customer_id}", response_model=schemas.CustomerOut)
def get_customer(customer_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return _summary_or_404(db, customer_id, current_user)


@router.get("/{customer_id}/ledger", response_model=schemas.PaginatedResponse[schemas.CustomerCreditEntryOut])
def get_ledger(
    customer_id: int,
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(20, ge=1, le=_MAX_PAGE_SIZE, description="Items per page (max 100)"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Returns the credit/udhaar ledger for a customer with pagination.
    Returns {items, total, page, page_size} — same shape as /medicines.
    """
    # Verify the customer belongs to this tenant
    customer = db.query(models.Customer).filter_by(
        id=customer_id, tenant_id=current_user.tenant_id
    ).first()
    if not customer:
        raise HTTPException(404, "Customer not found")

    # Cap page_size defensively
    page_size = min(page_size, _MAX_PAGE_SIZE)

    base_query = (
        db.query(models.CustomerCredit)
        .filter_by(customer_id=customer_id)
        .order_by(models.CustomerCredit.created_at.desc())
    )

    total = base_query.count()
    items = (
        base_query
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return schemas.PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/{customer_id}/credit/charge", response_model=schemas.CustomerOut)
def charge_credit(customer_id: int, payload: schemas.CreditChargeRequest, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    try:
        customer_service.charge_credit(db, customer_id, payload.amount, tenant_id=current_user.tenant_id, note=payload.note)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _summary_or_404(db, customer_id, current_user)


@router.post("/{customer_id}/credit/payment", response_model=schemas.CustomerOut)
def record_payment(customer_id: int, payload: schemas.CreditPaymentRequest, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    try:
        customer_service.record_payment(db, customer_id, payload.amount, tenant_id=current_user.tenant_id, note=payload.note)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _summary_or_404(db, customer_id, current_user)