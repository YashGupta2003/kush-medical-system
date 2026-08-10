from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_owner
from app.services import trust_score_service

router = APIRouter(prefix="/trust-score", dependencies=[Depends(require_owner)], tags=["trust-score"])

@router.get("/distributors")
def compute_all_distributor_scores(db: Session = Depends(get_db)):
    """Compute and return trust scores for all distributors."""
    try:
        return trust_score_service.compute_all_distributor_scores(db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/distributors/{distributor_id}")
def compute_trust_score(
    distributor_id: int, 
    medicine_id: Optional[int] = None, 
    db: Session = Depends(get_db)
):
    """Compute and return trust score for a specific distributor, optionally scoped by medicine."""
    try:
        return trust_score_service.compute_trust_score(db, distributor_id, medicine_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/batch-collisions")
def detect_batch_collisions(
    days: int = Query(365, ge=1), 
    db: Session = Depends(get_db)
):
    """Detect overlapping batch numbers that might indicate counterfeit goods or data entry errors."""
    try:
        return trust_score_service.detect_batch_collisions(db, days)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/medicine/{medicine_id}/rate-consistency")
def compute_rate_consistency(
    medicine_id: int, 
    db: Session = Depends(get_db)
):
    """Analyze the rate consistency for a given medicine to flag volatile pricing."""
    try:
        return trust_score_service.compute_rate_consistency(db, medicine_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
