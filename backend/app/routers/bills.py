import os
import uuid
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app import models, schemas
from app.services.tasks import process_bill_task, reprocess_region_task
from app.services.image_preprocessing import correct_orientation
from app.deps import get_current_user, get_current_user_flexible
from app.events.bus import event_bus
from app.events.events import BillConfirmedEvent, BillUploadedEvent
from app.services.duplicate_checker import compute_file_checksum, check_duplicate_bill
from app.services import duplicate_service
from app.core.logging import get_logger

logger = get_logger("bills_router")

router = APIRouter(prefix="/bills", tags=["bills"])


def _resolve_distributor(db: Session, name: Optional[str]) -> Optional[models.Distributor]:
    if not name:
        return None
    distributor = db.query(models.Distributor).filter_by(name=name.upper()).first()
    if not distributor:
        distributor = models.Distributor(name=name.upper())
        db.add(distributor)
        db.flush()
    return distributor


def _create_queued_bill(db: Session, file_bytes: bytes, filename: str,
                         distributor_name: Optional[str], invoice_no: Optional[str],
                         invoice_date: Optional[str]) -> models.Bill:
    file_bytes = correct_orientation(file_bytes)
    checksum = compute_file_checksum(file_bytes)

    distributor = _resolve_distributor(db, distributor_name)
    is_dup, dup_reason, _ = check_duplicate_bill(
        db, file_bytes=file_bytes, invoice_no=invoice_no,
        distributor_id=distributor.id if distributor else None
    )
    if is_dup:
        logger.warning(f"[DUPLICATE CHECK] {dup_reason}")

    os.makedirs(settings.upload_dir, exist_ok=True)
    ext = os.path.splitext(filename or "")[1] or ".jpg"
    saved_name = f"{uuid.uuid4().hex}{ext}"
    saved_path = os.path.join(settings.upload_dir, saved_name)
    with open(saved_path, "wb") as f:
        f.write(file_bytes)

    inv_date = None
    if invoice_date:
        try:
            inv_date = datetime.strptime(invoice_date, "%Y-%m-%d")
        except ValueError:
            inv_date = None
    now = inv_date or datetime.utcnow()

    bill = models.Bill(
        distributor_id=distributor.id if distributor else None,
        invoice_no=invoice_no,
        invoice_date=inv_date,
        year=now.year,
        month=now.month,
        image_path=saved_path,
        status="queued",
        checksum=checksum,
    )
    db.add(bill)
    db.flush()

    event_bus.publish(BillUploadedEvent(
        bill_id=bill.id, filename=filename,
        distributor_name=distributor_name, checksum=checksum
    ))
    return bill


@router.post("/upload", response_model=schemas.UploadAcceptedResponse)
async def upload_bill(
    file: UploadFile = File(...),
    distributor_name: Optional[str] = Form(None),
    invoice_no: Optional[str] = Form(None),
    invoice_date: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Single-bill upload. Returns IMMEDIATELY with a bill_id + task_id -
    OCR/parsing happens in the background (Celery worker), not in this
    request. Poll GET /bills/{bill_id}/status to know when it's ready to
    review.
    """
    file_bytes = await file.read()
    bill = _create_queued_bill(db, file_bytes, file.filename, distributor_name, invoice_no, invoice_date)
    db.commit()

    task = process_bill_task.delay(bill.id)
    bill.celery_task_id = task.id
    db.commit()

    dup_bill = duplicate_service.find_confirmed_duplicate(db, bill.distributor_id, bill.invoice_no)
    dup_warning = None
    if dup_bill:
        conf_date = dup_bill.uploaded_at.strftime('%Y-%m-%d') if dup_bill.uploaded_at else "earlier date"
        dup_warning = f"Warning: Bill #{dup_bill.id} from this distributor with invoice number '{bill.invoice_no}' was already confirmed on {conf_date}."

    return schemas.UploadAcceptedResponse(bill_id=bill.id, task_id=task.id, status=bill.status, duplicate_warning=dup_warning)


@router.post("/upload-batch", response_model=List[schemas.UploadAcceptedResponse])
async def upload_bills_batch(
    files: List[UploadFile] = File(...),
    distributor_name: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Upload MULTIPLE bill photos in one request (e.g. a whole stack of
    invoices received in one delivery). Each one gets its own Bill row and
    its own background task, processed independently and in parallel by
    the Celery worker(s) - one slow/bad photo doesn't block the rest.
    """
    if not files:
        raise HTTPException(400, "No files provided")

    responses = []
    for file in files:
        file_bytes = await file.read()
        bill = _create_queued_bill(db, file_bytes, file.filename, distributor_name, None, None)
        db.commit()
        task = process_bill_task.delay(bill.id)
        bill.celery_task_id = task.id
        db.commit()

        dup_bill = duplicate_service.find_confirmed_duplicate(db, bill.distributor_id, bill.invoice_no)
        dup_warning = None
        if dup_bill:
            conf_date = dup_bill.uploaded_at.strftime('%Y-%m-%d') if dup_bill.uploaded_at else "earlier date"
            dup_warning = f"Warning: Bill #{dup_bill.id} from this distributor with invoice number '{bill.invoice_no}' was already confirmed on {conf_date}."

        responses.append(schemas.UploadAcceptedResponse(bill_id=bill.id, task_id=task.id, status=bill.status, duplicate_warning=dup_warning))

    return responses



@router.get("/{bill_id}/status", response_model=schemas.BillStatusOut)
def get_bill_status(bill_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """
    Lightweight polling endpoint - frontend calls this every couple seconds
    after upload instead of re-fetching the full bill (with all items) each
    time. Once status is 'pending_review' or 'needs_attention', switch to
    fetching the full bill via GET /bills/{bill_id}.
    """
    bill = db.query(models.Bill).get(bill_id)
    if not bill:
        raise HTTPException(404, "Bill not found")
    return schemas.BillStatusOut(
        id=bill.id, status=bill.status,
        ocr_confidence=float(bill.ocr_confidence) if bill.ocr_confidence is not None else None,
        needs_attention_reason=bill.needs_attention_reason,
        processing_error=bill.processing_error,
    )


@router.get("/{bill_id}", response_model=schemas.BillOut)
def get_bill(bill_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    bill = db.query(models.Bill).get(bill_id)
    if not bill:
        raise HTTPException(404, "Bill not found")
    return _bill_to_out(db, bill)


@router.get("/{bill_id}/image")
def get_bill_image(bill_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user_flexible)):
    from fastapi.responses import FileResponse
    bill = db.query(models.Bill).get(bill_id)
    if not bill or not bill.image_path or not os.path.exists(bill.image_path):
        raise HTTPException(404, "Bill image not found")
    return FileResponse(bill.image_path)


@router.post("/{bill_id}/items", response_model=schemas.BillItemOut)
def add_manual_item(bill_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """
    Adds one blank line item to a bill for manual entry - the fallback for
    bills where OCR found no table at all (needs_attention_reason already
    tells the user "this bill needs fully manual entry on the review
    screen", but until this endpoint existed there was no way to actually
    do that). The new row behaves exactly like an OCR-extracted one from
    here on: it goes through the same medicine-link, cost-calc, and
    /bills/confirm code paths, no special-casing needed anywhere else.
    """
    bill = db.query(models.Bill).get(bill_id)
    if not bill:
        raise HTTPException(404, "Bill not found")
    if bill.status == "confirmed":
        raise HTTPException(400, "This bill has already been confirmed - items can no longer be added.")

    item = models.BillItem(
        bill_id=bill.id,
        raw_name="",
        qty=0, free_qty=0,
        discount_pct=0, special_discount_pct=0, gst_pct=0,
        match_confidence=0, match_status="unmatched",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{bill_id}/items/{item_id}")
def remove_bill_item(bill_id: int, item_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Removes a line item before confirming - a manually-added row entered by mistake, or a bad OCR extraction."""
    bill = db.query(models.Bill).get(bill_id)
    if not bill:
        raise HTTPException(404, "Bill not found")
    if bill.status == "confirmed":
        raise HTTPException(400, "This bill has already been confirmed - items can no longer be removed.")

    item = db.query(models.BillItem).filter_by(id=item_id, bill_id=bill_id).first()
    if not item:
        raise HTTPException(404, "Item not found")
    db.delete(item)
    db.commit()
    return {"status": "ok"}


@router.get("", response_model=List[schemas.BillOut])
def list_bills(
    year: Optional[int] = None,
    month: Optional[int] = None,
    status: Optional[str] = None,
    distributor_name: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    q = db.query(models.Bill)
    if year:
        q = q.filter(models.Bill.year == year)
    if month:
        q = q.filter(models.Bill.month == month)
    if status:
        q = q.filter(models.Bill.status == status)
    if distributor_name:
        q = q.join(models.Distributor).filter(models.Distributor.name == distributor_name.upper())
    bills = q.order_by(models.Bill.uploaded_at.desc()).all()
    return [_bill_to_out(db, b) for b in bills]


@router.post("/{bill_id}/reprocess-region", response_model=schemas.RegionOcrResponse)
def reprocess_region(bill_id: int, payload: schemas.RegionOcrRequest, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """
    Powers 'click-to-fill': the frontend sends the pixel rectangle the user
    just drew on the (possibly zoomed/panned) bill image, mapped back to
    original image coordinates. This re-runs OCR on JUST that crop and
    returns the text, which the frontend offers as a fill-in for whichever
    field the user had selected.

    Runs synchronously (not queued) since the crop is small and this needs
    to feel instant in the UI - FastAPI runs sync 'def' endpoints in a
    thread pool automatically, so this doesn't block other requests.
    """
    bill = db.query(models.Bill).get(bill_id)
    if not bill:
        raise HTTPException(404, "Bill not found")

    result = reprocess_region_task.apply(
        args=[bill_id, payload.x0, payload.y0, payload.x1, payload.y1]
    ).get()

    if result.get("status") != "ok":
        raise HTTPException(422, result.get("detail", "Could not read that region"))

    return schemas.RegionOcrResponse(text=result["text"], confidence=result["confidence"])


@router.post("/confirm", response_model=List[schemas.ChangeSummaryItem])
def confirm_bill(payload: schemas.ConfirmBillRequest, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """
    Confirms a bill and publishes BillConfirmedEvent to the central EventBus pipeline.
    Decoupled subscribers automatically process stock increments, batch/expiry creation,
    learned distributor mappings, rate history auditing, and cache invalidation.
    """
    bill = db.query(models.Bill).get(payload.bill_id)
    if not bill:
        raise HTTPException(404, "Bill not found")

    # Apply optional invoice_no and distributor_name corrections if provided during review
    if payload.distributor_name is not None and payload.distributor_name.strip():
        dist = _resolve_distributor(db, payload.distributor_name.strip())
        bill.distributor_id = dist.id
    if payload.invoice_no is not None:
        bill.invoice_no = payload.invoice_no

    # Hard gate check for duplicate confirmed invoice before confirming
    dup_bill = duplicate_service.find_confirmed_duplicate(
        db, distributor_id=bill.distributor_id, invoice_no=bill.invoice_no, exclude_bill_id=bill.id
    )
    if dup_bill:
        conf_date = dup_bill.uploaded_at.strftime('%Y-%m-%d') if dup_bill.uploaded_at else "earlier date"
        raise HTTPException(
            status_code=409,
            detail=f"Bill #{dup_bill.id} with invoice number '{bill.invoice_no}' was already confirmed on {conf_date}. Please double-check or update the invoice number before confirming."
        )

    if bill.status == "confirmed":
        raise HTTPException(400, "This bill has already been confirmed.")

    changes: List[schemas.ChangeSummaryItem] = []

    # Instantiate domain event
    event = BillConfirmedEvent(
        bill_id=bill.id,
        db=db,
        items_edits=payload.items,
        distributor_id=bill.distributor_id,
    )
    # Attach changes output collector
    object.__setattr__(event, "changes_output", changes)

    # Publish event to pipeline subscribers
    event_bus.publish(event)

    bill.status = "confirmed"
    db.commit()
    return changes


def _bill_to_out(db: Session, bill: models.Bill) -> schemas.BillOut:
    items_out = []
    for item in bill.items:
        suggested_name = None
        if item.medicine_id:
            med = db.query(models.Medicine).get(item.medicine_id)
            suggested_name = med.particulars if med else None
        io = schemas.BillItemOut.model_validate(item)
        io.suggested_medicine_name = suggested_name
        items_out.append(io)

    return schemas.BillOut(
        id=bill.id,
        distributor_name=bill.distributor.name if bill.distributor else None,
        invoice_no=bill.invoice_no,
        invoice_date=bill.invoice_date,
        year=bill.year,
        month=bill.month,
        total_amount=float(bill.total_amount) if bill.total_amount is not None else None,
        status=bill.status.value if hasattr(bill.status, "value") else str(bill.status),
        uploaded_at=bill.uploaded_at,
        ocr_confidence=float(bill.ocr_confidence) if bill.ocr_confidence is not None else None,
        needs_attention_reason=bill.needs_attention_reason,
        processing_error=bill.processing_error,
        items=items_out,
    )