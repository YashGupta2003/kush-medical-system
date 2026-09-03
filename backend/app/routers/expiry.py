from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas
from app.services import expiry_service
from app.deps import get_current_user

router = APIRouter(prefix="/expiry", dependencies=[Depends(get_current_user)],tags=["expiry"])


@router.get("/dashboard", response_model=list[schemas.ExpiryBatchOut])
def expiry_dashboard(
    days: int = Query(90, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return expiry_service.get_expiry_dashboard(db, tenant_id=current_user.tenant_id, days=days)


@router.get("/summary", response_model=schemas.ExpirySummary)
def expiry_summary(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return expiry_service.get_expiry_summary(db, tenant_id=current_user.tenant_id)


@router.get("/missing", response_model=list[schemas.MissingExpiryBatch])
def missing_expiry(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return expiry_service.get_missing_expiry_batches(db, tenant_id=current_user.tenant_id)


@router.patch("/batch/{batch_id}")
def fill_expiry(batch_id: int, payload: schemas.FillExpiryRequest, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    ok = expiry_service.fill_missing_expiry(db, tenant_id=current_user.tenant_id, batch_id=batch_id, expiry_date=payload.expiry_date)
    if not ok:
        raise HTTPException(404, "Batch not found")
    return {"status": "ok"}
