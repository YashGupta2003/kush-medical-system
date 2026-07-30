from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.deps import get_current_user

router = APIRouter(prefix="/medicines", dependencies=[Depends(get_current_user)], tags=["medicines"])


def _mask_cost_for_staff(medicines: List[models.Medicine], current_user: models.User):
    if current_user.role == "owner":
        return medicines
    for m in medicines:
        m.net_rate = None
    return medicines


@router.get("", response_model=schemas.PaginatedMedicines)
def list_or_search_medicines(
    q: Optional[str] = Query(None, description="Optional partial name filter"),
    page: int = 1,
    page_size: int = 50,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(models.Medicine)
    if q:
        query = query.filter(models.Medicine.particulars.ilike(f"%{q}%"))
    query = query.order_by(models.Medicine.particulars)

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    items = _mask_cost_for_staff(items, current_user)

    return schemas.PaginatedMedicines(items=items, total=total, page=page, page_size=page_size)


@router.get("/barcode/{code}", response_model=schemas.BarcodeLookupResult)
def lookup_by_barcode(code: str, db: Session = Depends(get_db)):
    from app.services import stock_service

    medicine = db.query(models.Medicine).filter(models.Medicine.barcode == code).first()
    if not medicine:
        return schemas.BarcodeLookupResult(found=False)

    snapshot = stock_service.get_stock_snapshot(db, medicine.id)
    return schemas.BarcodeLookupResult(found=True, medicine=medicine, stock=snapshot)


@router.patch("/{medicine_id}/barcode", response_model=schemas.MedicineOut)
def assign_barcode(medicine_id: int, payload: schemas.BarcodeAssignRequest, db: Session = Depends(get_db)):
    medicine = db.query(models.Medicine).get(medicine_id)
    if not medicine:
        raise HTTPException(404, "Medicine not found")

    clash = db.query(models.Medicine).filter(
        models.Medicine.barcode == payload.barcode, models.Medicine.id != medicine_id
    ).first()
    if clash:
        raise HTTPException(400, f"This barcode is already linked to '{clash.particulars}'")

    medicine.barcode = payload.barcode
    db.commit()
    db.refresh(medicine)
    return medicine

@router.patch("/{medicine_id}/composition", response_model=schemas.MedicineOut)
def update_composition(medicine_id: int, payload: schemas.CompositionUpdate, db: Session = Depends(get_db)):
    from app.services import composition_service

    medicine = composition_service.set_medicine_composition(db, medicine_id, payload.composition)
    if not medicine:
        raise HTTPException(404, "Medicine not found")
    db.commit()
    db.refresh(medicine)
    return medicine


@router.get("/{medicine_id}", response_model=schemas.MedicineOut)
def get_medicine(medicine_id: int, db: Session = Depends(get_db)):
    medicine = db.query(models.Medicine).get(medicine_id)
    if not medicine:
        raise HTTPException(404, "Medicine not found")
    return medicine


@router.get("/{medicine_id}/history", response_model=List[schemas.RateHistoryOut])
def get_rate_history(medicine_id: int, db: Session = Depends(get_db)):
    history = (
        db.query(models.RateHistory)
        .filter(models.RateHistory.medicine_id == medicine_id)
        .order_by(models.RateHistory.changed_at.desc())
        .all()
    )
    return history
