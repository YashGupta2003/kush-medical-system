"""
Demand Forecasting endpoints (Pillar 6, Part 1). Extends the Smart Reorder
Point Engine's flat 30-day average (reorder_intelligence.py) with a
seasonal, statsmodels-based forecast where there's enough history to
support one - see forecast_service.py's module docstring.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas
from app.services import forecast_service
from app.deps import get_current_user

router = APIRouter(prefix="/forecast", dependencies=[Depends(get_current_user)], tags=["forecast"])


@router.get("/medicine/{medicine_id}", response_model=schemas.DemandForecastOut)
def get_forecast(
    medicine_id: int,
    periods: int = Query(14, ge=1, le=90),
    history_days: int = Query(180, ge=30, le=365),
    db: Session = Depends(get_db),
):
    try:
        return forecast_service.get_demand_forecast(db, medicine_id, periods=periods, history_days=history_days)
    except ValueError as e:
        raise HTTPException(404, str(e))