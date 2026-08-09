"""
Anomaly / Pilferage Detection endpoints (Pillar 6, Part 2 & 3). Owner-only
- flags staff-attributable patterns and rate-change irregularities, both
sensitive enough to match this codebase's existing convention of
reserving oversight/financial screens (Analytics, GST) for the Owner.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas
from app.services import anomaly_service, anomaly_explainer_service
from app.deps import require_owner

router = APIRouter(prefix="/anomalies", dependencies=[Depends(require_owner)], tags=["anomalies"])


@router.get("/price-jumps", response_model=schemas.PriceJumpAnomalyResult)
def price_jump_anomalies(days: int = 180, db: Session = Depends(get_db)):
    return anomaly_service.detect_price_jump_anomalies(db, days=days)


@router.get("/stock-adjustments", response_model=schemas.StockAdjustmentAnomalyResult)
def stock_adjustment_anomalies(days: int = 90, db: Session = Depends(get_db)):
    return anomaly_service.detect_stock_adjustment_anomalies(db, days=days)


@router.post("/explain", response_model=schemas.AnomalyExplainResponse)
def explain_anomaly(payload: schemas.AnomalyExplainRequest):
    """
    Takes one flagged anomaly item (as returned by the two endpoints
    above) and returns a plain-English explanation - see
    anomaly_explainer_service.py's module docstring for why this is a
    presentation layer on top of real statistics, not a replacement for
    it.
    """
    explanation = anomaly_explainer_service.explain_anomaly(payload.anomaly)
    return schemas.AnomalyExplainResponse(explanation=explanation)