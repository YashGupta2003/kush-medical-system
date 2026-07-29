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
    from app.services.pipeline import BillProcessingPipeline
    db = SessionLocal()
    try:
        task_id = getattr(self.request, "id", None)
        pipeline = BillProcessingPipeline(bill_id=bill_id, db=db, task_id=task_id)
        return pipeline.run()
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
