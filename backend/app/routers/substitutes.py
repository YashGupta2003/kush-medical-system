"""
Substitute Medicine Suggestion - a standalone feature area, deliberately kept
in its own router/service pair rather than folded into medicines.py, so it
can grow (e.g. a future "same therapeutic class" suggestion) without
crowding the core medicines CRUD file.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas
from app.services import composition_service
from app.deps import get_current_user

router = APIRouter(prefix="/substitutes", dependencies=[Depends(get_current_user)], tags=["substitutes"])


@router.get("/search", response_model=list[schemas.SubstituteMedicineItem])
def search_substitutes(
    q: str = Query(..., min_length=2, description="A salt name or full composition text, e.g. 'Paracetamol'"),
    in_stock_only: bool = True,
    db: Session = Depends(get_db),
):
    """
    Free-text substitute search - powers the 'search by salt' mode on the
    Substitute Finder screen. Also works for a doctor's prescription salt
    name typed directly, not just a medicine name.
    """
    return composition_service.find_substitutes(db, q, in_stock_only=in_stock_only)


@router.get("/availability", response_model=schemas.SaltAvailability)
def check_availability(
    q: str = Query(..., min_length=2),
    db: Session = Depends(get_db),
):
    """
    Powers the smarter "no results" messaging: tells the frontend whether a
    salt genuinely isn't in the master list at all, vs it IS in the master
    list but nothing carrying it currently has stock.
    """
    return composition_service.check_salt_availability(db, q)


@router.get("/for-medicine/{medicine_id}", response_model=schemas.MedicineSubstituteResult)
def substitutes_for_medicine(
    medicine_id: int,
    in_stock_only: bool = True,
    db: Session = Depends(get_db),
):
    """
    'This exact medicine (e.g. Crocin) is out of stock - what else works' -
    looks up medicine_id's own composition and searches from there. Works
    even when medicine_id itself has zero stock.
    """
    result = composition_service.get_medicine_substitutes(db, medicine_id, in_stock_only=in_stock_only)
    if result["medicine"] is None:
        raise HTTPException(404, "Medicine not found")
    return result
