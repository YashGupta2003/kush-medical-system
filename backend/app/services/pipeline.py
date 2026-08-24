"""
Unified Bill Processing Pipeline.
Encapsulates the multi-step background OCR, parsing, matching, and cost calculation workflow
into a modular, testable pipeline class with event emission and structured logging.
"""
import time
import traceback
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.core.logging import get_logger
from app.services import image_preprocessing
from app.services.ocr_service import run_ocr
from app.services.bill_parser import parse_bill_words
from app.services.cost_calculator import compute_cost_per_unit, cross_check_amount
from app.services.matcher import find_best_match
from app.events.bus import event_bus
from app.events.events import BillProcessedEvent

logger = get_logger("bill_pipeline")


class BillProcessingPipeline:
    """
    Step-by-step pipeline for background processing of pharmacy purchase bills.
    """
    def __init__(self, bill_id: int, db: Session, task_id: str = None):
        self.bill_id = bill_id
        self.db = db
        self.task_id = task_id
        self.start_time = time.time()

    def run(self) -> Dict[str, Any]:
        """Executes all pipeline stages sequentially."""
        logger.info(f"Starting BillProcessingPipeline for Bill #{self.bill_id}")
        bill = self.db.get(models.Bill, self.bill_id)
        if not bill:
            logger.error(f"Pipeline failed: Bill #{self.bill_id} not found in database")
            return {"status": "error", "detail": f"Bill {self.bill_id} not found"}

        try:
            bill.status = "processing"
            if self.task_id:
                bill.celery_task_id = self.task_id
            self.db.commit()

            # Stage 1: Image Reading & Preprocessing
            logger.info(f"Stage 1: Preprocessing image for Bill #{self.bill_id} ({bill.image_path})")
            with open(bill.image_path, "rb") as f:
                original_bytes = f.read()

            try:
                prep = image_preprocessing.preprocess_bill_image(original_bytes)
                ocr_input_bytes = prep.image_bytes
                bill.preprocessing_notes = "; ".join(prep.warnings) or "no issues"
            except Exception as prep_error:
                logger.warning(f"Preprocessing skipped due to error: {prep_error}")
                ocr_input_bytes = original_bytes
                bill.preprocessing_notes = f"preprocessing skipped due to error: {prep_error}"

            # Stage 2: OCR Execution
            logger.info(f"Stage 2: Running OCR engine on Bill #{self.bill_id}")
            ocr_result = run_ocr(ocr_input_bytes)
            bill.raw_ocr_text = ocr_result.full_text
            bill.ocr_confidence = round(ocr_result.avg_confidence, 2)
            logger.info(f"OCR completed: avg_confidence={bill.ocr_confidence}%")

            # Stage 3: Row & Table Parsing
            logger.info(f"Stage 3: Parsing OCR word bounding boxes into structured rows")
            from app.services.bill_parser import parse_bill_advanced
            parsed_rows = parse_bill_advanced(bill.raw_ocr_text, ocr_result.words)
            logger.info(f"Parsed {len(parsed_rows)} line item rows from OCR text")

            low_confidence = ocr_result.avg_confidence < settings.ocr_confidence_threshold
            no_rows_found = len(parsed_rows) == 0

            if no_rows_found:
                bill.status = "needs_attention"
                bill.needs_attention_reason = (
                    "No table structure could be detected - photo may be too blurry, "
                    "skewed, or this distributor's layout isn't recognized yet. "
                    "This bill needs fully manual entry on the review screen."
                )
                self.db.commit()
                event_bus.publish(BillProcessedEvent(
                    bill_id=self.bill_id, status=bill.status,
                    ocr_confidence=float(bill.ocr_confidence or 0), items_count=0
                ))
                return {"status": "needs_attention", "bill_id": self.bill_id, "reason": "no_rows_found"}

            # Stage 4: Cost Calculation & Master Matching
            logger.info(f"Stage 4: Computing costs and linking items against master rate list")
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

                medicine, confidence, match_status = find_best_match(
                    self.db, f.get("name", ""), distributor_id=bill.distributor_id
                )

                item = models.BillItem(
                    bill_id=bill.id,
                    medicine_id=medicine.id if medicine else None,
                    raw_name=str(f.get("name", "") or "")[:255].strip(),
                    pack=str(f.get("pack") or "")[:50],
                    batch=str(f.get("batch") or "")[:50],
                    exp_date=str(f.get("exp_date") or "")[:20],
                    qty=qty, free_qty=free_qty,
                    mrp=f.get("mrp"), rate=rate,
                    discount_pct=discount_pct, special_discount_pct=special_discount_pct,
                    gst_pct=gst_pct,
                    amount=f.get("amount", expected_amount),
                    computed_cost_per_unit=cost_per_unit,
                    match_confidence=confidence,
                    match_status=match_status,
                )
                self.db.add(item)
                total += float(f.get("amount", expected_amount) or 0)

            bill.total_amount = total
            bill.status = "needs_attention" if low_confidence else "pending_review"
            if low_confidence:
                bill.needs_attention_reason = (
                    f"OCR confidence ({ocr_result.avg_confidence:.0f}%) was below the "
                    f"{settings.ocr_confidence_threshold:.0f}% threshold - double-check every "
                    f"field carefully before confirming."
                )

            self.db.commit()

            # Stage 5: Event Emission
            event_bus.publish(BillProcessedEvent(
                bill_id=self.bill_id, status=bill.status,
                ocr_confidence=float(bill.ocr_confidence or 0), items_count=len(parsed_rows)
            ))

            elapsed = round(time.time() - self.start_time, 2)
            logger.info(f"Pipeline successfully completed for Bill #{self.bill_id} in {elapsed}s")
            return {"status": bill.status, "bill_id": self.bill_id, "items_extracted": len(parsed_rows)}

        except Exception as e:
            self.db.rollback()
            bill = self.db.get(models.Bill, self.bill_id)
            if bill:
                bill.status = "failed"
                bill.processing_error = f"{e}\n{traceback.format_exc()[-2000:]}"
                self.db.commit()
            logger.error(f"Pipeline execution failed for Bill #{self.bill_id}: {e}", exc_info=True)
            return {"status": "failed", "bill_id": self.bill_id, "error": str(e)}
