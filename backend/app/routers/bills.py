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
    # Fix EXIF-tagged or physically-sideways photos BEFORE anything else
    # touches the file - the saved image on disk, the review screen's
    # <img>, preprocessing, OCR, and reprocess-region all read this same
    # file, so correcting it once here fixes all of them at once.
    file_bytes = correct_orientation(file_bytes)

    os.makedirs(settings.upload_dir, exist_ok=True)
    ext = os.path.splitext(filename or "")[1] or ".jpg"
    saved_name = f"{uuid.uuid4().hex}{ext}"
    saved_path = os.path.join(settings.upload_dir, saved_name)
    with open(saved_path, "wb") as f:
        f.write(file_bytes)

    distributor = _resolve_distributor(db, distributor_name)

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
    )
    db.add(bill)
    db.flush()
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

    return schemas.UploadAcceptedResponse(bill_id=bill.id, task_id=task.id, status=bill.status)


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
        responses.append(schemas.UploadAcceptedResponse(bill_id=bill.id, task_id=task.id, status=bill.status))

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
    The ONLY place the master rate list actually gets updated. Every change
    is logged to rate_history. Returns a change summary: exactly which
    column changed for which medicine.
    """
    bill = db.query(models.Bill).get(payload.bill_id)
    if not bill:
        raise HTTPException(404, "Bill not found")
    if bill.status == "confirmed":
        # Prevents accidentally double-adding this bill's stock (and
        # double-logging rate_history) if /confirm is somehow called twice
        # for the same bill.
        raise HTTPException(400, "This bill has already been confirmed.")

    changes: List[schemas.ChangeSummaryItem] = []
    items_by_id = {item.id: item for item in bill.items}

    for edit in payload.items:
        item = items_by_id.get(edit.id)
        if item is None:
            continue

        for attr in ("raw_name", "qty", "free_qty", "mrp", "rate",
                     "discount_pct", "special_discount_pct", "gst_pct", "exp_date"):
            value = getattr(edit, attr)
            if value is not None:
                setattr(item, attr, value)

        from app.services.cost_calculator import compute_cost_per_unit
        item.computed_cost_per_unit = compute_cost_per_unit(
            rate=float(item.rate or 0), qty=float(item.qty or 0),
            discount_pct=float(item.discount_pct or 0),
            special_discount_pct=float(item.special_discount_pct or 0),
            gst_pct=float(item.gst_pct or 0), free_qty=float(item.free_qty or 0),
        )

        if edit.medicine_id:
            item.medicine_id = edit.medicine_id
            item.match_status = "manual"
            # LEARNING LOOP: remember this exact (distributor, raw name) ->
            # medicine choice, so future bills with the same raw text from
            # the same distributor auto-link instantly next time instead of
            # relying on fuzzy matching again.
            from app.services.matcher import save_learned_mapping
            save_learned_mapping(
                db, raw_name=item.raw_name, medicine_id=edit.medicine_id,
                distributor_id=bill.distributor_id,
            )

        item.match_status = "confirmed" if item.match_status != "unmatched" else "unmatched"

        if edit.apply_to_master_list and item.medicine_id:
            medicine = db.query(models.Medicine).get(item.medicine_id)
            old_rate, old_mrp = medicine.net_rate, medicine.mrp
            new_rate = item.computed_cost_per_unit
            new_mrp = item.mrp if item.mrp else medicine.mrp

            rate_changed = old_rate != new_rate
            mrp_changed = old_mrp != new_mrp

            if rate_changed or mrp_changed:
                db.add(models.RateHistory(
                    medicine_id=medicine.id, bill_item_id=item.id,
                    old_net_rate=old_rate, new_net_rate=new_rate,
                    old_mrp=old_mrp, new_mrp=new_mrp,
                ))
                if rate_changed:
                    changes.append(schemas.ChangeSummaryItem(
                        medicine_name=medicine.particulars, field="net_rate",
                        old_value=float(old_rate) if old_rate is not None else None,
                        new_value=float(new_rate) if new_rate is not None else None,
                    ))
                if mrp_changed:
                    changes.append(schemas.ChangeSummaryItem(
                        medicine_name=medicine.particulars, field="mrp",
                        old_value=float(old_mrp) if old_mrp is not None else None,
                        new_value=float(new_mrp) if new_mrp is not None else None,
                    ))
                medicine.net_rate = new_rate
                medicine.mrp = new_mrp

        # STOCK TRACKING: regardless of whether this item's rate/MRP is
        # applied to the master list, the physical stock DID arrive at the
        # shop - so stock is always incremented for any matched item, tied
        # to the low-stock-alert and reorder-list feature.
        from app.services import stock_service, expiry_service
        if item.medicine_id:
            stock_service.add_stock_from_confirmed_bill_item(db, item)
            # EXPIRY TRACKING: create a batch record (parses item.exp_date;
            # if it can't be parsed, the batch still gets created with a
            # NULL expiry so it shows up in the "missing expiry" prompt
            # instead of vanishing.
            expiry_service.create_batch_from_confirmed_item(db, item)

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
        status=bill.status,
        uploaded_at=bill.uploaded_at,
        ocr_confidence=float(bill.ocr_confidence) if bill.ocr_confidence is not None else None,
        needs_attention_reason=bill.needs_attention_reason,
        processing_error=bill.processing_error,
        items=items_out,
    )