from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/medicines", tags=["medicines"])


@router.get("", response_model=schemas.PaginatedMedicines)
def list_or_search_medicines(
    q: Optional[str] = Query(None, description="Optional partial name filter"),
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
):
    """
    Without `q`: returns the FULL master list, paginated - this is what
    powers "show me everything" browsing on the search page.
    With `q`: same endpoint, filtered - this is the Ctrl+F replacement.
    Either way the response always includes `total`, so the frontend can
    show "showing 50 of 4977" and a Load more button.
    """
    query = db.query(models.Medicine)
    if q:
        query = query.filter(models.Medicine.particulars.ilike(f"%{q}%"))
    query = query.order_by(models.Medicine.particulars)

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return schemas.PaginatedMedicines(items=items, total=total, page=page, page_size=page_size)


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