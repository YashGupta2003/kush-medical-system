import os
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Request
from app.core.rate_limit import limiter
from fastapi import Depends
from app.config import settings
from fastapi import UploadFile, File, Form, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.config import settings
from app import models, schemas
from app.core.upload_validation import validate_upload
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


def _resolve_distributor(db: Session, name: Optional[str], tenant_id: Optional[int] = None) -> Optional[models.Distributor]:
    if not name:
        return None
    # BUG FIX: Filter by tenant_id to prevent cross-tenant distributor sharing.
    # Previously the lookup ignored tenant_id, allowing distributors from one
    # tenant to be linked to another tenant's bills.
    distributor = db.query(models.Distributor).filter(
        models.Distributor.name == name.upper(),
        models.Distributor.tenant_id == tenant_id,
    ).first()
    if not distributor:
        distributor = models.Distributor(name=name.upper(), tenant_id=tenant_id)
        db.add(distributor)
        db.flush()
    return distributor


def _create_queued_bill(db: Session, file_bytes: bytes, filename: str, tenant_id: int,
                         distributor_name: Optional[str], invoice_no: Optional[str],
                         invoice_date: Optional[str]) -> models.Bill:
    file_bytes = correct_orientation(file_bytes)
    checksum = compute_file_checksum(file_bytes)

    distributor = _resolve_distributor(db, distributor_name, tenant_id=tenant_id)
    is_dup, dup_reason, _ = check_duplicate_bill(
        db, file_bytes=file_bytes, invoice_no=invoice_no,
        distributor_id=distributor.id if distributor else None
    )
    if is_dup:
        logger.warning(f"[DUPLICATE CHECK] {dup_reason}")

    os.makedirs(settings.upload_dir, exist_ok=True)
    ext = os.path.splitext(filename or "")[1].lower() or ".jpg"
    if ext == ".pdf":
        ext = ".png"  # ensure_image_bytes converts PDFs to PNG
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
    now = inv_date or datetime.now(timezone.utc)

    bill = models.Bill(
        tenant_id=tenant_id,
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
@limiter.limit(settings.rate_limit_ocr)
async def upload_bill(request: Request, 
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
    file_bytes = validate_upload(file)
    bill = _create_queued_bill(db, file_bytes, file.filename, current_user.tenant_id, distributor_name, invoice_no, invoice_date)
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
        file_bytes = validate_upload(file)
        bill = _create_queued_bill(db, file_bytes, file.filename, current_user.tenant_id, distributor_name, None, None)
        db.commit()
        task = process_bill_task.delay(bill.id)
        bill.celery_task_id = task.id
        db.commit()

        # BUG FIX: At batch-upload time invoice_no is always None — the OCR task
        # hasn't run yet. A duplicate check against None invoice_no is meaningless.
        # Skip it here; the confirm_bill flow (which runs post-OCR) will do the
        # real duplicate check once the invoice number is known.
        dup_warning = None

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
    bill = db.query(models.Bill).options(joinedload(models.Bill.items).joinedload(models.BillItem.medicine), joinedload(models.Bill.distributor)).filter(models.Bill.id == bill_id, models.Bill.tenant_id == current_user.tenant_id).first()
    if not bill:
        raise HTTPException(404, "Bill not found")
    return schemas.BillStatusOut(
        id=bill.id, status=bill.status,
        ocr_confidence=float(bill.ocr_confidence) if bill.ocr_confidence is not None else None,
        needs_attention_reason=bill.needs_attention_reason,
        processing_error=bill.processing_error,
        distributor_id=bill.distributor_id,
    )


@router.get("/{bill_id}", response_model=schemas.BillOut)
def get_bill(bill_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    bill = db.query(models.Bill).options(joinedload(models.Bill.items).joinedload(models.BillItem.medicine), joinedload(models.Bill.distributor)).filter(models.Bill.id == bill_id, models.Bill.tenant_id == current_user.tenant_id).first()
    if not bill:
        raise HTTPException(404, "Bill not found")
    return _bill_to_out(db, bill)


@router.get("/{bill_id}/image")
def get_bill_image(bill_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user_flexible)):
    from fastapi.responses import FileResponse
    bill = db.query(models.Bill).options(joinedload(models.Bill.items).joinedload(models.BillItem.medicine), joinedload(models.Bill.distributor)).filter(models.Bill.id == bill_id, models.Bill.tenant_id == current_user.tenant_id).first()
    if not bill or not bill.image_path or not os.path.exists(bill.image_path):
        raise HTTPException(404, "Bill image not found")
    # BUG FIX: PDFs are converted to .png by ensure_image_bytes (line 60 above),
    # so image_path NEVER ends in .pdf. The original check was a no-op.
    # Use .png detection to correctly set image/png MIME type.
    media_type = "image/png" if bill.image_path.lower().endswith(".png") else "image/jpeg"
    return FileResponse(bill.image_path, media_type=media_type)


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
    bill = db.query(models.Bill).options(joinedload(models.Bill.items).joinedload(models.BillItem.medicine), joinedload(models.Bill.distributor)).filter(models.Bill.id == bill_id, models.Bill.tenant_id == current_user.tenant_id).first()
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
    bill = db.query(models.Bill).options(joinedload(models.Bill.items).joinedload(models.BillItem.medicine), joinedload(models.Bill.distributor)).filter(models.Bill.id == bill_id, models.Bill.tenant_id == current_user.tenant_id).first()
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


@router.get("", response_model=schemas.PaginatedResponse[schemas.BillOut])
def list_bills(
    year: Optional[int] = None,
    month: Optional[int] = None,
    status: Optional[str] = None,
    distributor_name: Optional[str] = None,
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Paginated bill listing. Use page/page_size for pagination.
    Defaults: page=1, page_size=20. Max page_size=100 to prevent OOM crashes.
    BUG FIX #1: Uses joinedload(Bill.items) to eliminate N+1 query trap.
    BUG FIX #2: Pagination prevents loading all bills into RAM at once.
    """
    # Build the base filter query (no joinedload yet, so COUNT is accurate)
    base_q = db.query(models.Bill).filter(models.Bill.tenant_id == current_user.tenant_id)
    if year:
        base_q = base_q.filter(models.Bill.year == year)
    if month:
        base_q = base_q.filter(models.Bill.month == month)
    if status:
        base_q = base_q.filter(models.Bill.status == status)
    if distributor_name:
        base_q = base_q.join(models.Distributor).filter(models.Distributor.name == distributor_name.upper())

    # BUG FIX: COUNT before applying joinedload (joinedload generates JOINs that can
    # inflate the row count when a bill has multiple items — use the clean base query).
    total = base_q.count()

    # BUG FIX #1: eager-load items + distributor in ONE query — eliminates
    # the 1+N SQL queries that were fired per bill in _bill_to_out()
    q = base_q.options(
        joinedload(models.Bill.items).joinedload(models.BillItem.medicine),
        joinedload(models.Bill.distributor),
    )
    offset = (page - 1) * page_size
    bills = q.order_by(models.Bill.uploaded_at.desc()).offset(offset).limit(page_size).all()
    return schemas.PaginatedResponse(
        items=[_bill_to_out(db, b) for b in bills],
        total=total,
        page=page,
        page_size=page_size,
    )


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
    bill = db.query(models.Bill).options(joinedload(models.Bill.items).joinedload(models.BillItem.medicine), joinedload(models.Bill.distributor)).filter(models.Bill.id == bill_id, models.Bill.tenant_id == current_user.tenant_id).first()
    if not bill:
        raise HTTPException(404, "Bill not found")

    result = reprocess_region_task(bill_id, payload.x0, payload.y0, payload.x1, payload.y1)

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
    bill = db.query(models.Bill).filter(models.Bill.id == payload.bill_id, models.Bill.tenant_id == current_user.tenant_id).first()
    if not bill:
        raise HTTPException(404, "Bill not found")

    if bill.status == "confirmed":
        raise HTTPException(400, "This bill has already been confirmed.")

    # Apply optional invoice_no and distributor_name corrections if provided during review
    if payload.distributor_name is not None and payload.distributor_name.strip():
        dist = _resolve_distributor(db, payload.distributor_name.strip(), tenant_id=current_user.tenant_id)
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

    # Calculate ADM field corrections before DB rows are mutated
    if bill.distributor_id and bill.detected_header_tokens:
        import json
        from app.services.distributor_memory_service import learn_from_confirmed_bill
        
        field_corrections = {}
        items_by_id = {item.id: item for item in bill.items}
        
        for edit in payload.items:
            db_item = items_by_id.get(edit.id)
            if not db_item:
                continue
            
            for attr in ("raw_name", "qty", "free_qty", "mrp", "rate", 
                         "discount_pct", "special_discount_pct", "gst_pct", "exp_date"):
                submitted_val = getattr(edit, attr, None)
                if submitted_val is not None:
                    db_val = getattr(db_item, attr, None)
                    # Use float conversion for numeric comparisons to avoid str/Decimal mismatches
                    if isinstance(submitted_val, (int, float)) and isinstance(db_val, (int, float)):
                        is_corrected = float(submitted_val) != float(db_val)
                    else:
                        is_corrected = str(submitted_val).strip() != str(db_val).strip()
                    
                    # If this field has ever been submitted across any item, track if it was corrected
                    if attr not in field_corrections or is_corrected:
                        field_corrections[attr] = is_corrected
                        
        try:
            detected_data = json.loads(bill.detected_header_tokens)
            header_tokens = detected_data.get("header_tokens", [])
            column_field_map = detected_data.get("column_field_map", {})
            if header_tokens:
                learn_from_confirmed_bill(
                    db, current_user.tenant_id, bill.distributor_id,
                    header_tokens, column_field_map, field_corrections
                )
        except Exception as e:
            logger.error(f"[CONFIRM BILL] ADM learning failed silently: {e}", exc_info=True)

    # BUG FIX #5: Publish event TRANSACTIONALLY.
    # transactional=True means: if ANY subscriber raises an exception, the
    # EventBus re-raises after all subscribers have been attempted. We then
    # rollback the DB session here, preventing partial state (e.g. stock
    # incremented but expiry entry never created). This is the "poor-man's
    # Outbox Pattern" — all side-effects commit atomically or not at all.
    try:
        event_bus.publish(event, transactional=True)
        bill.status = "confirmed"
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(f"[CONFIRM BILL] Atomic event pipeline failed for Bill #{bill.id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=(
                f"Bill confirmation failed: one or more processing steps errored. "
                f"All changes have been rolled back — no partial state was committed. "
                f"Please retry. Details: {exc}"
            ),
        )
    return changes


def _bill_to_out(db: Session, bill: models.Bill) -> schemas.BillOut:
    """
    BUG FIX #1: Uses the already-loaded item.medicine relationship (set by joinedload
    in list_bills) instead of issuing a db.query(Medicine).get() call per item.
    This eliminates the N+1 query trap: 50 bills = 1 query, not 51.
    For single-bill fetches (get_bill), also loads medicine via relationship to
    avoid an extra query per item.
    """
    items_out = []
    for item in bill.items:
        # Use already-loaded relationship (medicine was joinedloaded) — no extra DB hit
        suggested_name = item.medicine.particulars if item.medicine else None
        io = schemas.BillItemOut.model_validate(item)
        io.suggested_medicine_name = suggested_name
        items_out.append(io)

    return schemas.BillOut(
        id=bill.id,
        distributor_id=bill.distributor_id,
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