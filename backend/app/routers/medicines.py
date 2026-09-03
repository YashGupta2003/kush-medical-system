from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.deps import get_current_user

import re

router = APIRouter(prefix="/medicines", dependencies=[Depends(get_current_user)], tags=["medicines"])

@router.post("", response_model=schemas.MedicineOut)
def create_medicine(
    payload: schemas.MedicineCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    from app.services import stock_service

    norm = re.sub(r'[^a-zA-Z0-9]', '', payload.particulars.upper())
    existing = db.query(models.Medicine).filter(
        models.Medicine.tenant_id == current_user.tenant_id,
        models.Medicine.normalized_name == norm
    ).first()
    if existing:
        raise HTTPException(400, "Medicine with this name already exists")
    
    new_med = models.Medicine(
        tenant_id=current_user.tenant_id,
        particulars=payload.particulars,
        normalized_name=norm,
        unit=payload.unit,
        mrp=payload.mrp,
        net_rate=payload.net_rate,
        company=payload.company,
        stockist=payload.stockist,
        current_stock=payload.current_stock or 0,
        low_stock_threshold=payload.low_stock_threshold,
        barcode=payload.barcode,
        composition=payload.composition
    )
    db.add(new_med)
    db.commit()
    db.refresh(new_med)

    if new_med.current_stock > 0:
        stock_service.record_adjustment(
            db, new_med.id, new_med.current_stock, "Initial stock upon creation", created_by_user_id=current_user.id
        )
        db.refresh(new_med)

    return new_med


def _mask_cost_for_staff(medicines: List[models.Medicine], current_user: models.User):
    if current_user.role == "owner":
        return medicines
    out = []
    for m in medicines:
        out_m = schemas.MedicineOut.model_validate(m)
        out_m.net_rate = None
        out.append(out_m)
    return out


@router.get(
    "",
    summary="List / search medicines",
    description="Returns a paginated list of medicines.",
)
def list_or_search_medicines(
    q: Optional[str] = Query(None, description="Optional partial name/composition filter"),
    after_id: Optional[int] = Query(None, description="Cursor: fetch medicines with id > after_id."),
    limit: int = Query(50, ge=1, le=500, description="Number of items per page."),
    page: int = Query(1, ge=1, description="Page number."),
    page_size: int = Query(50, ge=1, le=500, description="Items per page."),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if after_id is not None:
        base_query = db.query(models.Medicine).filter(
            models.Medicine.tenant_id == current_user.tenant_id,
            models.Medicine.id > after_id
        )
        if q:
            base_query = base_query.filter(models.Medicine.particulars.ilike(f"%{q}%"))

        rows = base_query.order_by(models.Medicine.id.asc()).limit(limit + 1).all()

        has_next = len(rows) > limit
        items = rows[:limit]
        items = _mask_cost_for_staff(items, current_user)

        next_cursor = items[-1].id if has_next and items else None

        return schemas.CursorPaginatedMedicines(
            items=items,
            next_cursor=next_cursor,
            limit=limit,
        )
    else:
        query = db.query(models.Medicine).filter(models.Medicine.tenant_id == current_user.tenant_id)
        if q:
            query = query.filter(models.Medicine.particulars.ilike(f"%{q}%"))
        query = query.order_by(models.Medicine.particulars)

        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()
        items = _mask_cost_for_staff(items, current_user)

        return schemas.PaginatedMedicines(items=items, total=total, page=page, page_size=page_size)


@router.get("/barcode/{code:path}", response_model=schemas.BarcodeLookupResult)
def lookup_by_barcode(code: str, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    from app.services import stock_service

    medicine = db.query(models.Medicine).filter(
        models.Medicine.tenant_id == current_user.tenant_id,
        models.Medicine.barcode == code
    ).first()
    if not medicine:
        return schemas.BarcodeLookupResult(found=False)

    snapshot = stock_service.get_stock_snapshot(db, medicine.id)
    return schemas.BarcodeLookupResult(found=True, medicine=medicine, stock=snapshot)


@router.patch("/{medicine_id}/barcode", response_model=schemas.MedicineOut)
def assign_barcode(medicine_id: int, payload: schemas.BarcodeAssignRequest, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    medicine = db.query(models.Medicine).filter(
        models.Medicine.id == medicine_id,
        models.Medicine.tenant_id == current_user.tenant_id
    ).first()
    if not medicine:
        raise HTTPException(404, "Medicine not found")

    clash = db.query(models.Medicine).filter(
        models.Medicine.tenant_id == current_user.tenant_id,
        models.Medicine.barcode == payload.barcode,
        models.Medicine.id != medicine_id
    ).first()
    if clash:
        raise HTTPException(400, f"This barcode is already linked to '{clash.particulars}'")

    medicine.barcode = payload.barcode
    db.commit()
    db.refresh(medicine)
    return medicine


@router.patch("/{medicine_id}/composition", response_model=schemas.MedicineOut)
def update_composition(medicine_id: int, payload: schemas.CompositionUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    from app.services import composition_service
    
    # Must check tenant_id first
    medicine = db.query(models.Medicine).filter(
        models.Medicine.id == medicine_id,
        models.Medicine.tenant_id == current_user.tenant_id
    ).first()
    if not medicine:
        raise HTTPException(404, "Medicine not found")

    medicine = composition_service.set_medicine_composition(db, medicine_id, payload.composition)
    db.commit()
    db.refresh(medicine)
    return medicine


@router.get("/{medicine_id}", response_model=schemas.MedicineOut)
def get_medicine(medicine_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    medicine = db.query(models.Medicine).filter(
        models.Medicine.id == medicine_id,
        models.Medicine.tenant_id == current_user.tenant_id
    ).first()
    if not medicine:
        raise HTTPException(404, "Medicine not found")
    return medicine


@router.get("/{medicine_id}/history", response_model=List[schemas.RateHistoryOut])
def get_rate_history(medicine_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # Verify ownership
    medicine = db.query(models.Medicine).filter(
        models.Medicine.id == medicine_id,
        models.Medicine.tenant_id == current_user.tenant_id
    ).first()
    if not medicine:
        raise HTTPException(404, "Medicine not found")

    history = (
        db.query(models.RateHistory)
        .filter(models.RateHistory.medicine_id == medicine_id)
        .order_by(models.RateHistory.changed_at.desc())
        .all()
    )
    return history
