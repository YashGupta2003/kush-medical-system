from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas
from app import models
from app.services import analytics_service

from app.deps import require_owner

router = APIRouter(prefix="/analytics", dependencies=[Depends(require_owner)], tags=["analytics"])


@router.get("/overview", response_model=schemas.AnalyticsOverview)
def overview(db: Session = Depends(get_db), current_user: models.User = Depends(require_owner)):
    """
    The top stat-card row - pulls from bills, stock, and expiry so the
    dashboard reflects the whole system's current state in one call.
    """
    return analytics_service.get_overview(db, tenant_id=current_user.tenant_id)


@router.get("/monthly-spend", response_model=list[schemas.MonthlySpendPoint])
def monthly_spend(
    months: int = Query(6, ge=1, le=24),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_owner)
):
    return analytics_service.get_monthly_spend(db, tenant_id=current_user.tenant_id, months=months)


@router.get("/distributor-breakdown", response_model=list[schemas.DistributorBreakdownItem])
def distributor_breakdown(
    year: Optional[int] = None,
    month: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_owner)
):
    """Defaults to the current calendar month if year/month aren't given."""
    return analytics_service.get_distributor_breakdown(db, tenant_id=current_user.tenant_id, year=year, month=month)


@router.get("/price-changes", response_model=list[schemas.PriceChangeItem])
def price_changes(
    days: int = Query(90, ge=1, le=730),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_owner)
):
    return analytics_service.get_price_changes(db, tenant_id=current_user.tenant_id, days=days, limit=limit)


@router.get("/top-medicines-by-spend", response_model=list[schemas.TopSpendItem])
def top_medicines_by_spend(
    year: Optional[int] = None,
    month: Optional[int] = None,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_owner)
):
    return analytics_service.get_top_medicines_by_spend(db, tenant_id=current_user.tenant_id, year=year, month=month, limit=limit)


@router.get("/top-selling", response_model=list[schemas.TopSellingItem])
def top_selling(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_owner)
):
    return analytics_service.get_top_selling(db, tenant_id=current_user.tenant_id, days=days, limit=limit)


@router.get("/inventory-valuation")
def inventory_valuation(db: Session = Depends(get_db), current_user: models.User = Depends(require_owner)):
    return analytics_service.get_inventory_valuation(db, tenant_id=current_user.tenant_id)


@router.get("/dead-stock")
def dead_stock(days: int = Query(90, ge=30, le=365), db: Session = Depends(get_db), current_user: models.User = Depends(require_owner)):
    return analytics_service.get_dead_stock(db, tenant_id=current_user.tenant_id, days=days)