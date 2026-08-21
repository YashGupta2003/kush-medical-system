from typing import List, Optional, Union
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


@router.get(
    "",
    summary="List / search medicines",
    description=(
        "Returns a paginated list of medicines.\n\n"
        "**Cursor (keyset) mode** — preferred for large catalogs:\n"
        "Pass `after_id=<last_id>` to fetch the next page. Uses "
        "`WHERE id > after_id LIMIT n` — hits the PK index directly, "
        "O(log N) regardless of depth.  Response includes `next_cursor` "
        "(None when no more pages).\n\n"
        "**Offset mode** — legacy, default when `after_id` is omitted:\n"
        "Use `page` + `page_size`.  Works fine for small catalogs but "
        "degrades for deep pages on large tables."
    ),
)
def list_or_search_medicines(
    q: Optional[str] = Query(None, description="Optional partial name/composition filter"),
    # --- Cursor pagination params ---
    after_id: Optional[int] = Query(
        None,
        description="Cursor: fetch medicines with id > after_id. Enables keyset pagination.",
    ),
    limit: int = Query(
        50,
        ge=1,
        le=500,
        description="Number of items per page (cursor mode). Max 500.",
    ),
    # --- Legacy offset pagination params ---
    page: int = Query(1, ge=1, description="Page number (offset mode, ignored when after_id is set)."),
    page_size: int = Query(50, ge=1, le=500, description="Items per page (offset mode, ignored when after_id is set)."),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    GET /medicines — supports both cursor and offset pagination.

    Cursor mode (after_id provided):
        GET /medicines?after_id=4532&limit=50
        Returns up to `limit` medicines with id > after_id, ordered by id ASC.
        Use `next_cursor` from the response as the next `after_id`.
        Response schema: CursorPaginatedMedicines

    Offset mode (after_id absent, default):
        GET /medicines?page=2&page_size=50
        Returns the Nth page using OFFSET arithmetic.
        Response schema: PaginatedMedicines
    """
    if after_id is not None:
        # ----------------------------------------------------------------
        # CURSOR (KEYSET) MODE
        # Query: WHERE id > after_id [AND particulars ILIKE %q%] ORDER BY id
        # This is a single index scan on the primary key — extremely fast
        # regardless of how many rows exist before the cursor position.
        # ----------------------------------------------------------------
        base_query = db.query(models.Medicine).filter(models.Medicine.id > after_id)
        if q:
            base_query = base_query.filter(models.Medicine.particulars.ilike(f"%{q}%"))

        # Fetch limit+1 rows so we can detect whether there's a next page
        # without a separate COUNT(*) query.
        rows = (
            base_query
            .order_by(models.Medicine.id.asc())
            .limit(limit + 1)
            .all()
        )

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
        # ----------------------------------------------------------------
        # OFFSET MODE (legacy — backward compatible)
        # Kept so that existing frontend code and tests continue to work
        # without any changes.
        # ----------------------------------------------------------------
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
    medicine = db.get(models.Medicine, medicine_id)
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
    medicine = db.get(models.Medicine, medicine_id)
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
