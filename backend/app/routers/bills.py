import os
import uuid
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app import models, schemas
from app.services.ocr_service import run_ocr
from app.services.bill_parser import parse_bill_words
from app.services.cost_calculator import compute_cost_per_unit, cross_check_amount
from app.services.matcher import find_best_match, normalize

router = APIRouter(prefix="/bills", tags=["bills"])


@router.post("/upload", response_model=schemas.BillOut)
async def upload_bill(
    file: UploadFile = File(...),
    distributor_name: Optional[str] = Form(None),
    invoice_no: Optional[str] = Form(None),
    invoice_date: Optional[str] = Form(None),   # "YYYY-MM-DD"
    db: Session = Depends(get_db),
):
    """
    Step 1 of the workflow: user photographs/uploads a bill.
    This runs OCR + parsing + cost calc + fuzzy matching and stores everything
    as a 'pending_review' bill. Nothing touches the master rate list yet -
    that only happens after the user explicitly confirms (see /confirm below).
    """
    os.makedirs(settings.upload_dir, exist_ok=True)
    ext = os.path.splitext(file.filename or "")[1] or ".jpg"
    saved_name = f"{uuid.uuid4().hex}{ext}"
    saved_path = os.path.join(settings.upload_dir, saved_name)

    image_bytes = await file.read()
    with open(saved_path, "wb") as f:
        f.write(image_bytes)

    raw_text, words = run_ocr(image_bytes)
    parsed_rows = parse_bill_words(words)

    if not parsed_rows:
        raise HTTPException(
            status_code=422,
            detail="Could not detect a table structure on this bill. "
                   "Try a clearer / flatter photo, or enter this bill's items manually.",
        )

    # resolve / create distributor
    distributor = None
    if distributor_name:
        distributor = db.query(models.Distributor).filter_by(name=distributor_name.upper()).first()
        if not distributor:
            distributor = models.Distributor(name=distributor_name.upper())
            db.add(distributor)
            db.flush()

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
        status="pending_review",
        raw_ocr_text=raw_text,
    )
    db.add(bill)
    db.flush()

    total = 0.0
    for row in parsed_rows:
        f = row.fields
        qty = f.get("qty", 0) or 0
        free_qty = f.get("free_qty", 0) or 0
        rate = f.get("rate", 0) or 0
        discount_pct = f.get("discount_pct", 0) or 0
        special_discount_pct = f.get("special_discount_pct", 0) or 0
        gst_pct = f.get("gst_pct", 0) or 0

        cost_per_unit = compute_cost_per_unit(
            rate=rate, qty=qty, discount_pct=discount_pct,
            special_discount_pct=special_discount_pct, gst_pct=gst_pct, free_qty=free_qty,
        )
        expected_amount = cross_check_amount(
            rate=rate, qty=qty, discount_pct=discount_pct,
            special_discount_pct=special_discount_pct, gst_pct=gst_pct,
        )

        medicine, confidence = find_best_match(db, f.get("name", ""))
        match_status = "auto" if medicine else "unmatched"

        item = models.BillItem(
            bill_id=bill.id,
            medicine_id=medicine.id if medicine else None,
            raw_name=f.get("name", "").strip(),
            pack=f.get("pack"),
            batch=f.get("batch"),
            exp_date=f.get("exp_date"),
            qty=qty,
            free_qty=free_qty,
            mrp=f.get("mrp"),
            rate=rate,
            discount_pct=discount_pct,
            special_discount_pct=special_discount_pct,
            gst_pct=gst_pct,
            amount=f.get("amount", expected_amount),
            computed_cost_per_unit=cost_per_unit,
            match_confidence=confidence,
            match_status=match_status,
        )
        db.add(item)
        total += float(f.get("amount", expected_amount) or 0)

    bill.total_amount = total
    db.commit()
    db.refresh(bill)

    return _bill_to_out(db, bill)


@router.get("/{bill_id}", response_model=schemas.BillOut)
def get_bill(bill_id: int, db: Session = Depends(get_db)):
    bill = db.query(models.Bill).get(bill_id)
    if not bill:
        raise HTTPException(404, "Bill not found")
    return _bill_to_out(db, bill)


@router.get("", response_model=List[schemas.BillOut])
def list_bills(
    year: Optional[int] = None,
    month: Optional[int] = None,
    distributor_name: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(models.Bill)
    if year:
        q = q.filter(models.Bill.year == year)
    if month:
        q = q.filter(models.Bill.month == month)
    if distributor_name:
        q = q.join(models.Distributor).filter(models.Distributor.name == distributor_name.upper())
    bills = q.order_by(models.Bill.uploaded_at.desc()).all()
    return [_bill_to_out(db, b) for b in bills]


@router.post("/confirm", response_model=List[schemas.ChangeSummaryItem])
def confirm_bill(payload: schemas.ConfirmBillRequest, db: Session = Depends(get_db)):
    """
    Step 2 of the workflow: user has reviewed the staged items (and possibly
    corrected some fields or picked the right medicine manually), and confirms.
    This is the ONLY place the master rate list actually gets updated, and
    every change is logged to rate_history so nothing is silently overwritten.
    Returns a change summary: exactly which column changed for which medicine.
    """
    bill = db.query(models.Bill).get(payload.bill_id)
    if not bill:
        raise HTTPException(404, "Bill not found")

    changes: List[schemas.ChangeSummaryItem] = []

    items_by_id = {item.id: item for item in bill.items}

    for edit in payload.items:
        item = items_by_id.get(edit.id)
        if item is None:
            continue

        # apply any user corrections to the staged row first
        for attr in ("raw_name", "qty", "free_qty", "mrp", "rate",
                     "discount_pct", "special_discount_pct", "gst_pct"):
            value = getattr(edit, attr)
            if value is not None:
                setattr(item, attr, value)

        item.computed_cost_per_unit = compute_cost_per_unit(
            rate=float(item.rate or 0), qty=float(item.qty or 0),
            discount_pct=float(item.discount_pct or 0),
            special_discount_pct=float(item.special_discount_pct or 0),
            gst_pct=float(item.gst_pct or 0), free_qty=float(item.free_qty or 0),
        )

        if edit.medicine_id:
            item.medicine_id = edit.medicine_id
            item.match_status = "manual"

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
        items=items_out,
    )
