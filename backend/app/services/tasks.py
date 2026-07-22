"""
The actual bill-processing pipeline, run as a Celery background task instead
of inline in the API request.

Flow: preprocess (OpenCV) -> OCR (Google/Tesseract) -> parse rows -> cost
calc -> fuzzy match -> write Bill + BillItems to DB -> set status.

Status ends as one of:
  'pending_review'   - normal case, OCR confidence was good
  'needs_attention'  - OCR confidence was low OR no table could be parsed
  'failed'           - an unexpected error occurred
"""
import traceback

from app.celery_app import celery_app
from app.database import SessionLocal
from app import models
from app.config import settings
from app.services import image_preprocessing
from app.services.ocr_service import run_ocr
from app.services.bill_parser import parse_bill_words
from app.services.cost_calculator import compute_cost_per_unit, cross_check_amount
from app.services.matcher import find_best_match


@celery_app.task(bind=True, name="process_bill")
def process_bill_task(self, bill_id: int):
    db = SessionLocal()
    try:
        bill = db.query(models.Bill).get(bill_id)
        if not bill:
            return {"status": "error", "detail": f"Bill {bill_id} not found"}

        bill.status = "processing"
        bill.celery_task_id = self.request.id
        db.commit()

        with open(bill.image_path, "rb") as f:
            original_bytes = f.read()

        try:
            prep = image_preprocessing.preprocess_bill_image(original_bytes)
            ocr_input_bytes = prep.image_bytes
            bill.preprocessing_notes = "; ".join(prep.warnings) or "no issues"
        except Exception as prep_error:
            ocr_input_bytes = original_bytes
            bill.preprocessing_notes = f"preprocessing skipped due to error: {prep_error}"

        ocr_result = run_ocr(ocr_input_bytes)
        bill.raw_ocr_text = ocr_result.full_text
        bill.ocr_confidence = round(ocr_result.avg_confidence, 2)

        parsed_rows = parse_bill_words(ocr_result.words)

        low_confidence = ocr_result.avg_confidence < settings.ocr_confidence_threshold
        no_rows_found = len(parsed_rows) == 0

        if no_rows_found:
            bill.status = "needs_attention"
            bill.needs_attention_reason = (
                "No table structure could be detected - photo may be too blurry, "
                "skewed, or this distributor's layout isn't recognized yet. "
                "This bill needs fully manual entry on the review screen."
            )
            db.commit()
            return {"status": "needs_attention", "bill_id": bill_id, "reason": "no_rows_found"}

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
                qty=qty, free_qty=free_qty,
                mrp=f.get("mrp"), rate=rate,
                discount_pct=discount_pct, special_discount_pct=special_discount_pct,
                gst_pct=gst_pct,
                amount=f.get("amount", expected_amount),
                computed_cost_per_unit=cost_per_unit,
                match_confidence=confidence,
                match_status=match_status,
            )
            db.add(item)
            total += float(f.get("amount", expected_amount) or 0)

        bill.total_amount = total
        bill.status = "needs_attention" if low_confidence else "pending_review"
        if low_confidence:
            bill.needs_attention_reason = (
                f"OCR confidence ({ocr_result.avg_confidence:.0f}%) was below the "
                f"{settings.ocr_confidence_threshold:.0f}% threshold - double-check every "
                f"field carefully before confirming."
            )
        db.commit()
        return {"status": bill.status, "bill_id": bill_id, "items_extracted": len(parsed_rows)}

    except Exception as e:
        db.rollback()
        bill = db.query(models.Bill).get(bill_id)
        if bill:
            bill.status = "failed"
            bill.processing_error = f"{e}\n{traceback.format_exc()[-2000:]}"
            db.commit()
        return {"status": "failed", "bill_id": bill_id, "error": str(e)}
    finally:
        db.close()


@celery_app.task(name="reprocess_region")
def reprocess_region_task(bill_id: int, x0: int, y0: int, x1: int, y1: int) -> dict:
    db = SessionLocal()
    try:
        bill = db.query(models.Bill).get(bill_id)
        if not bill:
            return {"status": "error", "detail": "Bill not found"}
        with open(bill.image_path, "rb") as f:
            original_bytes = f.read()
        crop_bytes = image_preprocessing.crop_region(original_bytes, x0, y0, x1, y1)
        result = run_ocr(crop_bytes)
        text = result.full_text.strip()
        return {"status": "ok", "text": text, "confidence": round(result.avg_confidence, 1)}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
    finally:
        db.close()
