from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas
from app.services import expiry_service

router = APIRouter(prefix="/expiry", tags=["expiry"])


@router.get("/dashboard", response_model=list[schemas.ExpiryBatchOut])
def expiry_dashboard(
    days: int = Query(90, ge=1, le=365),
    db: Session = Depends(get_db),
):
    return expiry_service.get_expiry_dashboard(db, days=days)


@router.get("/summary", response_model=schemas.ExpirySummary)
def expiry_summary(db: Session = Depends(get_db)):
    return expiry_service.get_expiry_summary(db)


@router.get("/missing", response_model=list[schemas.MissingExpiryBatch])
def missing_expiry(db: Session = Depends(get_db)):
    return expiry_service.get_missing_expiry_batches(db)


@router.patch("/batch/{batch_id}")
def fill_expiry(batch_id: int, payload: schemas.FillExpiryRequest, db: Session = Depends(get_db)):
    ok = expiry_service.fill_missing_expiry(db, batch_id, payload.expiry_date)
    if not ok:
        raise HTTPException(404, "Batch not found")
    return {"status": "ok"}
