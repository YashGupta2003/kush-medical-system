from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/medicines", tags=["medicines"])


@router.get("/search", response_model=List[schemas.MedicineOut])
def search_medicines(
    q: str = Query(..., min_length=1, description="Medicine name, partial match"),
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """
    The direct replacement for Ctrl+F in Excel: instant search by name,
    returns current MRP and current cost price (net_rate).
    """
    results = (
        db.query(models.Medicine)
        .filter(models.Medicine.particulars.ilike(f"%{q}%"))
        .order_by(models.Medicine.particulars)
        .limit(limit)
        .all()
    )
    return results


@router.get("/{medicine_id}", response_model=schemas.MedicineOut)
def get_medicine(medicine_id: int, db: Session = Depends(get_db)):
    medicine = db.query(models.Medicine).get(medicine_id)
    if not medicine:
        raise HTTPException(404, "Medicine not found")
    return medicine


@router.get("/{medicine_id}/history", response_model=List[schemas.RateHistoryOut])
def get_rate_history(medicine_id: int, db: Session = Depends(get_db)):
    """Full price-change timeline for one medicine - powers the trend graph."""
    history = (
        db.query(models.RateHistory)
        .filter(models.RateHistory.medicine_id == medicine_id)
        .order_by(models.RateHistory.changed_at.desc())
        .all()
    )
    return history
