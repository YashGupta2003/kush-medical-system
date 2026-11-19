import json
import os
import uuid
from datetime import datetime, timezone, date
from typing import Optional, List

from fastapi import APIRouter, Request, BackgroundTasks
from app.core.rate_limit import limiter
from fastapi import Depends
from app.config import settings
from fastapi import UploadFile, File, Form, HTTPException, Query
from sqlalchemy.exc import IntegrityError
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
from app.events.subscribers import handle_bill_confirmed_cache_invalidation
from app.services.duplicate_checker import compute_file_checksum, check_duplicate_bill
from app.services import duplicate_service
from app.core.logging import get_logger
from app.core.task_dispatch import dispatch_task

logger = get_logger("bills_router")

router = APIRouter(prefix="/bills", tags=["bills"])

CONFIRMABLE_BILL_STATUSES = {"pending_review", "needs_attention"}


def _request_id(request: Request) -> str:
    return getattr(getattr(request, "state", None), "request_id", "unknown")


def _supports_for_update(db: Session) -> bool:
    try:
        bind = db.get_bind()
        return bool(bind and bind.dialect.name not in ("sqlite",))
    except Exception:
        return False


def _set_bill_invoice_date_fields(bill: models.Bill, inv_date) -> None:
    """Apply invoice_date and keep derived year/month consistent."""
    if inv_date is None:
        bill.invoice_date = None
        # Preserve existing year/month when date unknown (legacy behavior).
        return
    if isinstance(inv_date, datetime):
        dt = inv_date
    elif isinstance(inv_date, date):
        dt = datetime(inv_date.year, inv_date.month, inv_date.day, tzinfo=timezone.utc)
    else:
        # Defensive: accept ISO-like strings if any caller passes them.
        try:
            dt = datetime.fromisoformat(str(inv_date))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid invoice_date")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    bill.invoice_date = dt
    bill.year = dt.year
    bill.month = dt.month


def _confirmed_invoice_key(tenant_id: Optional[int], distributor_id: Optional[int], invoice_no: Optional[str]) -> Optional[str]:
    norm = duplicate_service.normalize_invoice_no(invoice_no)
    if tenant_id is None or distributor_id is None or norm is None:
        return None
    return f"{tenant_id}:{distributor_id}:{norm}"


def _resolve_distributor(db: Session, name: Optional[str], tenant_id: Optional[int] = None) -> Optional[models.Distributor]:
    if not name:
        return None
    normalized_name = name.strip().upper()
    if not normalized_name:
        return None

    distributor = db.query(models.Distributor).filter(
        models.Distributor.name == normalized_name,
        models.Distributor.tenant_id == tenant_id,
    ).first()
    if distributor:
        return distributor

    try:
        with db.begin_nested():
            distributor = models.Distributor(name=normalized_name, tenant_id=tenant_id)
            db.add(distributor)
            db.flush()
            return distributor
    except IntegrityError:
        # Another request created the same tenant-scoped distributor concurrently.
        return db.query(models.Distributor).filter(
            models.Distributor.name == normalized_name,
            models.Distributor.tenant_id == tenant_id,
        ).first()


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
    background_tasks: BackgroundTasks,
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

    dispatch = dispatch_task(
        process_bill_task, bill.id, background_tasks=background_tasks
    )
    bill.celery_task_id = dispatch.task_id
    db.commit()
    if dispatch.executed:
        # Inline fallback may have already finished the pipeline in another
        # session; refresh before reporting status to the client.
        db.expire_all()
        db.refresh(bill)

    dup_bill = duplicate_service.find_confirmed_duplicate(db, bill.distributor_id, bill.invoice_no)
    dup_warning = None
    if dup_bill:
        conf_date = dup_bill.uploaded_at.strftime('%Y-%m-%d') if dup_bill.uploaded_at else "earlier date"
        dup_warning = f"Warning: Bill #{dup_bill.id} from this distributor with invoice number '{bill.invoice_no}' was already confirmed on {conf_date}."

    return schemas.UploadAcceptedResponse(
        bill_id=bill.id,
        task_id=dispatch.task_id,
        status=bill.status,
        duplicate_warning=dup_warning,
    )


@router.post("/upload-batch", response_model=List[schemas.UploadAcceptedResponse])
async def upload_bills_batch(
    background_tasks: BackgroundTasks,
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
        dispatch = dispatch_task(
            process_bill_task, bill.id, background_tasks=background_tasks
        )
        bill.celery_task_id = dispatch.task_id
        db.commit()
        if dispatch.executed:
            db.expire_all()
            db.refresh(bill)

        # BUG FIX: At batch-upload time invoice_no is always None — the OCR task
        # hasn't run yet. A duplicate check against None invoice_no is meaningless.
        # Skip it here; the confirm_bill flow (which runs post-OCR) will do the
        # real duplicate check once the invoice number is known.
        dup_warning = None

        responses.append(schemas.UploadAcceptedResponse(
            bill_id=bill.id,
            task_id=dispatch.task_id,
            status=bill.status,
            duplicate_warning=dup_warning,
        ))

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
        tenant_id=bill.tenant_id,
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
def confirm_bill(
    payload: schemas.ConfirmBillRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Confirms a bill and publishes BillConfirmedEvent to the central EventBus pipeline.
    Decoupled subscribers automatically process stock increments, batch/expiry creation,
    learned distributor mappings, rate history auditing, and graph sync. Cache
    invalidation (non-DB side effect) runs only after a successful commit.
    """
    req_id = _request_id(request)

    try:
        q = db.query(models.Bill).options(joinedload(models.Bill.items)).filter(
            models.Bill.id == payload.bill_id,
            models.Bill.tenant_id == current_user.tenant_id,
        )
        if _supports_for_update(db):
            q = q.with_for_update()
        bill = q.first()
        if not bill:
            raise HTTPException(404, "Bill not found")

        bill_status = bill.status.value if hasattr(bill.status, "value") else str(bill.status)
        if bill_status == "confirmed":
            raise HTTPException(400, "This bill has already been confirmed.")
        if bill_status not in CONFIRMABLE_BILL_STATUSES:
            raise HTTPException(
                status_code=409,
                detail=f"Bill cannot be confirmed from status '{bill_status}'.",
            )

        # Apply optional corrections if provided during review
        if payload.distributor_name is not None and payload.distributor_name.strip():
            dist = _resolve_distributor(db, payload.distributor_name.strip(), tenant_id=current_user.tenant_id)
            bill.distributor_id = dist.id
        if payload.invoice_no is not None:
            bill.invoice_no = payload.invoice_no
        if getattr(payload, "invoice_date", None) is not None:
            _set_bill_invoice_date_fields(bill, payload.invoice_date)

        # Validate edited items belong to this bill (prevent cross-bill/foreign edits).
        items_by_id = {item.id: item for item in bill.items}
        seen_item_ids = set()
        for edit in payload.items:
            if edit.id in seen_item_ids:
                raise HTTPException(status_code=400, detail="Duplicate bill item edit submitted")
            seen_item_ids.add(edit.id)
            if edit.id not in items_by_id:
                raise HTTPException(status_code=400, detail="One or more edited items do not belong to this bill")

        # Compute dedup key for DB guard (confirmed invoices only, when dedup-able).
        dedup_key = _confirmed_invoice_key(bill.tenant_id, bill.distributor_id, bill.invoice_no)
        bill.confirmed_invoice_key = dedup_key

        # Hard gate check for duplicate confirmed invoice before confirming.
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
        # Attach changes output collector and suppress pre-commit cache invalidation.
        object.__setattr__(event, "changes_output", changes)
        object.__setattr__(event, "skip_cache_invalidation", True)

        # ADM learning: isolate in savepoint so learning failures/partial flushes
        # cannot abort or corrupt the bill confirmation transaction.
        if bill.distributor_id and bill.detected_header_tokens:
            try:
                with db.begin_nested():
                    from app.services.distributor_memory_service import learn_from_confirmed_bill

                    field_corrections = {}
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

                    detected_data = json.loads(bill.detected_header_tokens)
                    header_tokens = detected_data.get("header_tokens", [])
                    column_field_map = detected_data.get("column_field_map", {})
                    if header_tokens:
                        learn_from_confirmed_bill(
                            db, current_user.tenant_id, bill.distributor_id,
                            header_tokens, column_field_map, field_corrections
                        )
            except Exception as adm_exc:
                # Savepoint rolled back by context manager on exception; log and continue.
                logger.error(
                    "[CONFIRM BILL] ADM learning failed for bill_id=%s request_id=%s: %s",
                    bill.id, req_id, adm_exc, exc_info=True,
                )

        # Publish event TRANSACTIONALLY (DB side effects). Cache invalidation is
        # intentionally skipped here and executed after commit.
        event_bus.publish(event, transactional=True)
        bill.status = "confirmed"
        db.commit()

        # Post-commit, non-DB side effects.
        try:
            handle_bill_confirmed_cache_invalidation(event)
        except Exception as cache_exc:
            logger.error(
                "[CONFIRM BILL] Post-commit cache invalidation failed for bill_id=%s request_id=%s: %s",
                bill.id, req_id, cache_exc, exc_info=True,
            )

        return changes

    except HTTPException:
        raise
    except IntegrityError as ie:
        db.rollback()
        # Likely DB uniqueness guard for confirmed invoices (race) or other constraint.
        logger.warning(
            "[CONFIRM BILL] Integrity error for bill_id=%s request_id=%s: %s",
            payload.bill_id, req_id, ie, exc_info=True,
        )
        # Best-effort: if the bill is now confirmed or a duplicate exists, report conflict.
        try:
            existing = db.query(models.Bill).filter(
                models.Bill.id == payload.bill_id,
                models.Bill.tenant_id == current_user.tenant_id,
            ).first()
            if existing and (existing.status == "confirmed" or getattr(existing.status, "value", None) == "confirmed"):
                raise HTTPException(status_code=409, detail="This bill has already been confirmed.")
        except HTTPException:
            raise
        except Exception:
            pass
        raise HTTPException(
            status_code=409,
            detail="A confirmed bill with this distributor and invoice number already exists, or the confirmation conflicts with existing data.",
        )
    except Exception as exc:
        db.rollback()
        logger.error(
            "[CONFIRM BILL] Confirmation failed for bill_id=%s request_id=%s: %s",
            payload.bill_id, req_id, exc, exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Bill confirmation failed. Please retry.",
        )


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
