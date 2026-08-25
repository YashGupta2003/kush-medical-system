"""
Prescription Intelligence Engine (PIE) — API Router.

Endpoints follow the same patterns as bills.py:
  - Upload returns immediately → process_prescription() runs synchronously
    (prescriptions are small, typically < 1 sec — no Celery needed)
  - GET endpoints for listing and item detail
  - PATCH endpoints for manual item linking and cart marking
  - POST /convert for marking a prescription as sold
"""
from typing import Optional, List

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel

from app.database import get_db
from app import models
from app.deps import get_current_user
from app.services import prescription_service
from app.core.logging import get_logger

logger = get_logger("prescriptions_router")

router = APIRouter(prefix="/prescriptions", tags=["prescriptions"])


# ---------------------------------------------------------------------------
# Pydantic response/request schemas (inline — no changes to schemas.py needed)
# ---------------------------------------------------------------------------
class PrescriptionItemOut(BaseModel):
    id: int
    raw_name: str
    medicine_id: Optional[int] = None
    medicine_name: Optional[str] = None
    substitute_medicine_id: Optional[int] = None
    substitute_medicine_name: Optional[str] = None
    qty_prescribed: Optional[float] = None
    dosage_instructions: Optional[str] = None
    match_confidence: Optional[float] = None
    match_status: str
    in_stock: Optional[bool] = None
    current_stock_qty: Optional[float] = None
    added_to_cart: bool

    class Config:
        from_attributes = True


class PrescriptionOut(BaseModel):
    id: int
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    status: str
    converted_to_sale: bool
    purchased_at: Optional[str] = None
    ocr_confidence: Optional[float] = None
    doctor_name: Optional[str] = None
    clinic_name: Optional[str] = None
    processing_error: Optional[str] = None
    created_at: str
    items: List[PrescriptionItemOut]

    class Config:
        from_attributes = True


class PaginatedPrescriptions(BaseModel):
    items: List[PrescriptionOut]
    total: int
    limit: int
    offset: int


class LinkMedicineRequest(BaseModel):
    medicine_id: int


class ConvertRequest(BaseModel):
    prescription_id: int


# ---------------------------------------------------------------------------
# Helper: convert ORM → response dict
# ---------------------------------------------------------------------------
def _item_to_out(item: models.PrescriptionItem) -> dict:
    return {
        "id": item.id,
        "raw_name": item.raw_name,
        "medicine_id": item.medicine_id,
        "medicine_name": item.medicine.particulars if item.medicine else None,
        "substitute_medicine_id": item.substitute_medicine_id,
        "substitute_medicine_name": (
            item.substitute_medicine.particulars if item.substitute_medicine else None
        ),
        "qty_prescribed": (
            float(item.qty_prescribed) if item.qty_prescribed is not None else None
        ),
        "dosage_instructions": item.dosage_instructions,
        "match_confidence": (
            float(item.match_confidence) if item.match_confidence is not None else None
        ),
        "match_status": str(
            item.match_status.value
            if hasattr(item.match_status, "value")
            else item.match_status
        ),
        "in_stock": item.in_stock,
        "current_stock_qty": (
            float(item.current_stock_qty)
            if item.current_stock_qty is not None
            else None
        ),
        "added_to_cart": item.added_to_cart,
    }


def _prescription_to_out(prescription: models.Prescription) -> dict:
    customer = prescription.customer
    return {
        "id": prescription.id,
        "customer_id": prescription.customer_id,
        "customer_name": customer.name if customer else None,
        "customer_phone": customer.phone if customer else None,
        "status": str(
            prescription.status.value
            if hasattr(prescription.status, "value")
            else prescription.status
        ),
        "converted_to_sale": prescription.converted_to_sale,
        "purchased_at": (
            prescription.purchased_at.isoformat()
            if prescription.purchased_at
            else None
        ),
        "ocr_confidence": (
            float(prescription.ocr_confidence)
            if prescription.ocr_confidence is not None
            else None
        ),
        "doctor_name": prescription.doctor_name,
        "clinic_name": prescription.clinic_name,
        "processing_error": prescription.processing_error,
        "created_at": prescription.created_at.isoformat(),
        "items": [_item_to_out(i) for i in prescription.items],
    }


def _load_prescription(db: Session, prescription_id: int) -> models.Prescription:
    """Eager-load a prescription with all relationships for API response."""
    return (
        db.query(models.Prescription)
        .options(
            joinedload(models.Prescription.items).joinedload(
                models.PrescriptionItem.medicine
            ),
            joinedload(models.Prescription.items).joinedload(
                models.PrescriptionItem.substitute_medicine
            ),
            joinedload(models.Prescription.customer),
        )
        .filter(models.Prescription.id == prescription_id)
        .first()
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("/upload")
async def upload_prescription(
    file: UploadFile = File(...),
    customer_phone: Optional[str] = Form(None),
    customer_name: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Upload a prescription image. Runs OCR + matching synchronously and returns
    the fully processed prescription with items and stock status.
    Optionally links to a customer by phone (creates customer if not found).
    """
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(400, "Empty file uploaded")

    # Resolve customer
    customer_id = None
    if customer_phone and customer_phone.strip():
        from app.services import customer_service

        customer = customer_service.get_or_create_customer(
            db,
            phone=customer_phone.strip(),
            name=customer_name.strip() if customer_name else None,
            consented=False,
        )
        db.flush()
        customer_id = customer.id

    # Create prescription row + process synchronously
    prescription = prescription_service.create_prescription(
        db,
        file_bytes,
        file.filename or "prescription.jpg",
        customer_id=customer_id,
    )
    db.commit()

    prescription_service.process_prescription(db, prescription.id)

    # Reload with all relationships for response
    loaded = _load_prescription(db, prescription.id)
    if not loaded:
        raise HTTPException(500, "Prescription processing failed to save")
    return _prescription_to_out(loaded)


@router.get("/uncollected")
def get_uncollected(
    minutes: int = Query(default=30, ge=5, le=240),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Returns prescriptions scanned but not converted to sale within `minutes` minutes."""
    return prescription_service.get_uncollected_prescriptions(db, minutes=minutes)


@router.get("")
def list_prescriptions(
    customer_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    result = prescription_service.list_prescriptions(
        db, customer_id=customer_id, status=status, limit=limit, offset=offset
    )
    ids = [p.id for p in result["items"]]
    if not ids:
        return {"items": [], "total": result["total"], "limit": limit, "offset": offset}

    prescriptions = (
        db.query(models.Prescription)
        .options(
            joinedload(models.Prescription.items).joinedload(
                models.PrescriptionItem.medicine
            ),
            joinedload(models.Prescription.items).joinedload(
                models.PrescriptionItem.substitute_medicine
            ),
            joinedload(models.Prescription.customer),
        )
        .filter(models.Prescription.id.in_(ids))
        .order_by(models.Prescription.created_at.desc())
        .all()
    )
    return {
        "items": [_prescription_to_out(p) for p in prescriptions],
        "total": result["total"],
        "limit": limit,
        "offset": offset,
    }


@router.post("/convert")
def convert_to_sale(
    payload: ConvertRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Called after POS sale is recorded from this prescription.
    Marks prescription as converted, closes the revenue-leakage tracking loop.
    """
    success = prescription_service.mark_converted(db, payload.prescription_id)
    if not success:
        raise HTTPException(404, "Prescription not found")
    db.commit()
    return {"status": "converted", "prescription_id": payload.prescription_id}


@router.get("/{prescription_id}")
def get_prescription(
    prescription_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    prescription = _load_prescription(db, prescription_id)
    if not prescription:
        raise HTTPException(404, "Prescription not found")
    return _prescription_to_out(prescription)


@router.patch("/{prescription_id}/items/{item_id}/link")
def link_item_to_medicine(
    prescription_id: int,
    item_id: int,
    payload: LinkMedicineRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Manually link a prescription item to a specific medicine (mirrors ReviewBill manual linking)."""
    item = prescription_service.update_item_medicine(
        db, prescription_id, item_id, payload.medicine_id
    )
    if not item:
        raise HTTPException(404, "Item or medicine not found")
    db.commit()

    # Reload with relationships
    db.refresh(item)
    if item.medicine:
        db.refresh(item.medicine)
    return _item_to_out(item)


@router.patch("/{prescription_id}/items/{item_id}/add-to-cart")
def mark_item_added_to_cart(
    prescription_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Mark a specific prescription item as added to the POS cart."""
    success = prescription_service.mark_item_added_to_cart(db, prescription_id, item_id)
    if not success:
        raise HTTPException(404, "Prescription item not found")
    db.commit()
    return {"status": "ok", "item_id": item_id, "added_to_cart": True}


@router.post("/{prescription_id}/abandon")
def abandon_prescription(
    prescription_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Staff dismisses the prescription without a sale."""
    success = prescription_service.mark_abandoned(db, prescription_id)
    if not success:
        raise HTTPException(404, "Prescription not found")
    db.commit()
    return {"status": "abandoned", "prescription_id": prescription_id}
