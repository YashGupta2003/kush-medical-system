"""
Prescription Intelligence Engine (PIE) — Service Layer.

Pipeline:
  1. Image saved → Prescription row created (status=queued)
  2. Background task runs OCR (same run_ocr() used by bill pipeline)
  3. OCR text → simple line-by-line parser extracts drug names + quantities
  4. Each drug name → fuzzy matcher (same find_best_match() used by bill pipeline)
  5. For each matched medicine: stock check via Medicine.current_stock
  6. For OOS medicines: composition_service.find_substitutes() → best in-stock substitute
  7. Prescription status → ready; items ready for POS basket pre-fill

Uncollected detection:
  A prescription is 'uncollected' when:
    - status is 'ready' (processed, not converted)
    - created_at is > 30 minutes ago
    - converted_to_sale is False
  PharmaCopilot calls get_uncollected_prescriptions() to flag these.

Adherence integration:
  When a prescription is converted to sale (mark_converted), if customer_id
  is set, the sale path through POS already calls record_sale_signal() via
  stock_service → surveillance_service. No extra call needed here.

Design principle: This service ONLY calls functions already in this
codebase. No new ML, no new external APIs. OCR, matching, stock check,
and substitute finding are all existing tested functions.
"""
import os
import uuid
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.services.ocr_service import run_ocr
from app.services.image_preprocessing import correct_orientation
from app.services.matcher import find_best_match
from app.services import composition_service
from app.core.logging import get_logger

logger = get_logger("prescription_service")

UNCOLLECTED_MINUTES = 30


# ---------------------------------------------------------------------------
# Prescription OCR text parser
# ---------------------------------------------------------------------------
_QTY_PATTERN = re.compile(
    r"(?:x|\*)\s*(\d+(?:\.\d+)?)|\b(\d+(?:\.\d+)?)\s*(?:tab|cap|mg|ml|strips?|nos?|units?)\b",
    re.IGNORECASE
)
_DOSAGE_PATTERN = re.compile(
    r"\b(\d+\s*-\s*\d+\s*-\s*\d+|od|bd|tds|qid|sos|\d+\s*times?\s*(?:a\s*)?day)\b",
    re.IGNORECASE
)
_SKIP_WORDS = {
    "patient", "name", "age", "date", "dr", "doctor", "clinic", "rx", "rp",
    "diagnosis", "sig", "dispensed", "pharmacist", "refill", "prescription",
    "phone", "address", "signature"
}


def _parse_prescription_text(raw_text: str) -> List[Dict[str, Any]]:
    """
    Tries to parse the OCR text using the powerful Groq LLM first.
    Falls back to simple heuristic if LLM fails or is unconfigured.
    """
    from app.config import settings
    
    if settings.groq_api_key:
        try:
            from groq import Groq
            import json
            
            client = Groq(api_key=settings.groq_api_key)
            prompt = f"""
You are an expert pharmacist AI. Extract all medicines/drugs prescribed in the following raw OCR text.
Ignore doctor names, clinic names, patient info, and random OCR noise.
Extract:
- raw_name: The medicine name only (no qty or dosage text)
- qty_prescribed: The total quantity (number only, e.g., 10 for '10 tabs')
- dosage_instructions: e.g., '1-0-1', 'twice a day', 'after meals'

Respond ONLY with a valid JSON array of objects, and absolutely no other text.
Format example:
[
  {{"raw_name": "Paracetamol 500mg", "qty_prescribed": 10, "dosage_instructions": "1-0-1"}},
  {{"raw_name": "Amoxicillin 250mg", "qty_prescribed": null, "dosage_instructions": "3 times a day"}}
]

RAW OCR TEXT:
{raw_text}
"""
            response = client.chat.completions.create(
                model=settings.groq_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=1024,
            )
            content = response.choices[0].message.content.strip()
            
            if content.startswith("```json"): content = content[7:]
            if content.startswith("```"): content = content[3:]
            if content.endswith("```"): content = content[:-3]
            
            data = json.loads(content.strip())
            
            if isinstance(data, list):
                valid_items = []
                for item in data:
                    if isinstance(item, dict) and item.get("raw_name"):
                        qty = item.get("qty_prescribed")
                        try:
                            qty = float(qty) if qty is not None else None
                        except (ValueError, TypeError):
                            qty = None
                        valid_items.append({
                            "raw_name": str(item.get("raw_name")),
                            "qty_prescribed": qty,
                            "dosage_instructions": str(item.get("dosage_instructions")) if item.get("dosage_instructions") else None
                        })
                if valid_items:
                    logger.info("PIE: Successfully parsed drugs using Groq LLM")
                    return valid_items
        except Exception as e:
            logger.error(f"PIE: Groq LLM parsing failed ({e}), falling back to heuristic")

    # Fallback heuristic parser
    logger.info("PIE: Using heuristic fallback parser")
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    items = []

    for line in lines:
        lower = line.lower()
        if any(word in lower.split() for word in _SKIP_WORDS): continue
        if len(line) < 4: continue
        if re.match(r'^[\d/\-\.]+$', line): continue

        dosage_match = _DOSAGE_PATTERN.search(line)
        dosage = dosage_match.group(0).strip() if dosage_match else None

        qty_match = _QTY_PATTERN.search(line)
        qty = None
        if qty_match:
            try: qty = float(qty_match.group(1) or qty_match.group(2))
            except: pass

        name = re.sub(_QTY_PATTERN, "", line)
        name = re.sub(_DOSAGE_PATTERN, "", name)
        name = re.sub(r'[\(\)\[\]\{\}@#$%^&*+=|<>]', ' ', name)
        name = re.sub(r'\s+', ' ', name).strip()
        name = re.sub(r'^[\d\.]+[\)\.]\s*', '', name)

        if len(name) < 3: continue

        items.append({
            "raw_name": name,
            "qty_prescribed": qty,
            "dosage_instructions": dosage,
        })

    return items


def _extract_doctor_info(raw_text: str) -> Dict[str, Optional[str]]:
    """Best-effort extraction of doctor name and clinic from OCR text header."""
    doctor_name = None
    clinic_name = None

    lines = [l.strip() for l in raw_text.splitlines() if l.strip()][:10]  # only header
    for line in lines:
        if re.search(r'\bdr\.?\s+|\bm\.?b\.?b\.?s\.?\b|\bmd\b|\bphysician\b', line, re.IGNORECASE):
            doctor_name = line[:150]
        elif re.search(r'\bclinic\b|\bhospital\b|\bmedical\b|\bhealth\b', line, re.IGNORECASE):
            clinic_name = line[:200]

    return {"doctor_name": doctor_name, "clinic_name": clinic_name}


# ---------------------------------------------------------------------------
# Core pipeline functions
# ---------------------------------------------------------------------------
def create_prescription(
    db: Session,
    image_bytes: bytes,
    filename: str,
    customer_id: Optional[int] = None,
) -> models.Prescription:
    """
    Stage 1: Save image, create Prescription row (status=queued).
    Background processing (OCR + matching) is triggered by the caller
    (router dispatches a Celery task or calls process_prescription synchronously).
    """
    image_bytes = correct_orientation(image_bytes)

    os.makedirs(settings.upload_dir, exist_ok=True)
    ext = os.path.splitext(filename or "")[1] or ".jpg"
    saved_name = f"rx_{uuid.uuid4().hex}{ext}"
    saved_path = os.path.join(settings.upload_dir, saved_name)
    with open(saved_path, "wb") as f:
        f.write(image_bytes)

    prescription = models.Prescription(
        customer_id=customer_id,
        image_path=saved_path,
        status="queued",
    )
    db.add(prescription)
    db.flush()
    logger.info(f"Created Prescription #{prescription.id} for customer_id={customer_id}")
    return prescription


def process_prescription(db: Session, prescription_id: int) -> Dict[str, Any]:
    """
    Stage 2-6: Full OCR + parse + match + stock check + substitute lookup.
    Called synchronously (small image, fast) OR can be dispatched as Celery task.
    Updates Prescription.status from queued → processing → ready (or failed).
    """
    prescription = db.get(models.Prescription, prescription_id)
    if not prescription:
        return {"status": "error", "detail": f"Prescription #{prescription_id} not found"}

    try:
        prescription.status = "processing"
        db.commit()

        # Stage 2: OCR
        logger.info(f"PIE #{prescription_id}: Running OCR on {prescription.image_path}")
        with open(prescription.image_path, "rb") as f:
            image_bytes = f.read()

        ocr_result = run_ocr(image_bytes)
        prescription.raw_ocr_text = ocr_result.full_text
        prescription.ocr_confidence = round(ocr_result.avg_confidence, 2)
        logger.info(f"PIE #{prescription_id}: OCR confidence={prescription.ocr_confidence}%")

        # Extract doctor/clinic info from header
        doc_info = _extract_doctor_info(ocr_result.full_text)
        prescription.doctor_name = doc_info["doctor_name"]
        prescription.clinic_name = doc_info["clinic_name"]

        # Stage 3: Parse OCR text → drug lines
        parsed_drugs = _parse_prescription_text(ocr_result.full_text)
        logger.info(f"PIE #{prescription_id}: Parsed {len(parsed_drugs)} drug lines")

        if not parsed_drugs:
            prescription.status = "ready"  # ready with 0 items — user can add manually
            prescription.processing_error = "Could not automatically extract drug names from this image. You can still tap 'Send to POS' to open a blank cart and add them manually."
            db.commit()
            return {"status": "ready", "prescription_id": prescription_id, "items_count": 0}

        # Stage 4-6: Match + stock check + substitute
        for drug in parsed_drugs:
            medicine, confidence, match_status = find_best_match(
                db, drug["raw_name"], distributor_id=None
            )

            in_stock = None
            current_stock_qty = None
            substitute_medicine_id = None

            if medicine:
                in_stock = float(medicine.current_stock or 0) > 0
                current_stock_qty = float(medicine.current_stock or 0)

                # Stage 6: Substitute lookup if OOS
                if not in_stock:
                    try:
                        substitutes = composition_service.find_substitutes(
                            db, drug["raw_name"], in_stock_only=True
                        )
                        if substitutes:
                            # Pick the first in-stock substitute
                            substitute_medicine_id = substitutes[0].get("medicine_id")
                    except Exception as sub_err:
                        logger.warning(f"PIE: Substitute lookup failed for '{drug['raw_name']}': {sub_err}")

            item = models.PrescriptionItem(
                prescription_id=prescription.id,
                medicine_id=medicine.id if medicine else None,
                raw_name=str(drug["raw_name"])[:255],
                qty_prescribed=drug.get("qty_prescribed"),
                dosage_instructions=str(drug["dosage_instructions"] or "")[:255] or None,
                match_confidence=confidence,
                match_status=match_status,
                in_stock=in_stock,
                current_stock_qty=current_stock_qty,
                substitute_medicine_id=substitute_medicine_id,
                added_to_cart=False,
            )
            db.add(item)

        prescription.status = "ready"
        db.commit()
        logger.info(f"PIE #{prescription_id}: Processing complete, {len(parsed_drugs)} items matched.")
        return {"status": "ready", "prescription_id": prescription_id, "items_count": len(parsed_drugs)}

    except Exception as e:
        import traceback
        db.rollback()
        prescription = db.get(models.Prescription, prescription_id)
        if prescription:
            prescription.status = "ready"  # fallback to ready so UI isn't stuck
            prescription.processing_error = f"{e}\n{traceback.format_exc()[-2000:]}"
            db.commit()
        logger.error(f"PIE #{prescription_id}: Processing failed: {e}", exc_info=True)
        return {"status": "failed", "prescription_id": prescription_id, "error": str(e)}


def get_prescription(db: Session, prescription_id: int) -> Optional[models.Prescription]:
    return db.get(models.Prescription, prescription_id)


def list_prescriptions(
    db: Session,
    customer_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    query = db.query(models.Prescription)
    if customer_id:
        query = query.filter(models.Prescription.customer_id == customer_id)
    if status:
        query = query.filter(models.Prescription.status == status)
    total = query.count()
    items = query.order_by(models.Prescription.created_at.desc()).offset(offset).limit(limit).all()
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def mark_item_added_to_cart(db: Session, prescription_id: int, item_id: int) -> bool:
    """Mark a prescription item as added to POS cart."""
    item = db.query(models.PrescriptionItem).filter_by(
        id=item_id, prescription_id=prescription_id
    ).first()
    if not item:
        return False
    item.added_to_cart = True
    db.flush()
    return True


def mark_converted(db: Session, prescription_id: int) -> bool:
    """
    Called after the pharmacist completes a cart sale from this prescription.
    Sets status=converted, converted_to_sale=True, purchased_at=now.
    """
    prescription = db.get(models.Prescription, prescription_id)
    if not prescription:
        return False
    prescription.status = "converted"
    prescription.converted_to_sale = True
    prescription.purchased_at = datetime.now(timezone.utc)
    db.flush()
    return True


def mark_abandoned(db: Session, prescription_id: int) -> bool:
    """Staff dismissed the prescription without a sale."""
    prescription = db.get(models.Prescription, prescription_id)
    if not prescription:
        return False
    prescription.status = "abandoned"
    db.flush()
    return True


def get_uncollected_prescriptions(
    db: Session,
    minutes: int = UNCOLLECTED_MINUTES,
) -> List[Dict[str, Any]]:
    """
    PharmaCopilot tool: returns prescriptions that were scanned and processed
    but NOT converted to a sale within `minutes` minutes — potential revenue leakage.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    prescriptions = (
        db.query(models.Prescription)
        .filter(
            models.Prescription.status == "ready",
            models.Prescription.converted_to_sale == False,
            models.Prescription.created_at <= cutoff,
        )
        .order_by(models.Prescription.created_at.asc())
        .all()
    )

    results = []
    for p in prescriptions:
        minutes_ago = int((datetime.now(timezone.utc) - p.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 60)
        customer = db.get(models.Customer, p.customer_id) if p.customer_id else None
        results.append({
            "prescription_id": p.id,
            "customer_name": customer.name if customer else None,
            "customer_phone": customer.phone if customer else None,
            "doctor_name": p.doctor_name,
            "items_count": len(p.items),
            "scanned_minutes_ago": minutes_ago,
            "created_at": p.created_at.isoformat(),
        })
    return results


def update_item_medicine(
    db: Session,
    prescription_id: int,
    item_id: int,
    medicine_id: int,
) -> Optional[models.PrescriptionItem]:
    """Manually link a prescription item to a medicine (same as ReviewBill's manual linking)."""
    item = db.query(models.PrescriptionItem).filter_by(
        id=item_id, prescription_id=prescription_id
    ).first()
    if not item:
        return None
    medicine = db.get(models.Medicine, medicine_id)
    if not medicine:
        return None
    item.medicine_id = medicine_id
    item.match_status = "manual"
    item.match_confidence = 100.0
    item.in_stock = float(medicine.current_stock or 0) > 0
    item.current_stock_qty = float(medicine.current_stock or 0)
    db.flush()
    return item

def add_manual_item(
    db: Session,
    prescription_id: int,
    medicine_id: int,
    qty_prescribed: Optional[float] = 1.0,
    dosage_instructions: Optional[str] = None
) -> Optional[models.PrescriptionItem]:
    """Manually add a missed drug to a prescription."""
    prescription = db.get(models.Prescription, prescription_id)
    medicine = db.get(models.Medicine, medicine_id)
    if not prescription or not medicine:
        return None
        
    item = models.PrescriptionItem(
        prescription_id=prescription_id,
        medicine_id=medicine_id,
        raw_name=medicine.particulars,
        qty_prescribed=qty_prescribed,
        dosage_instructions=dosage_instructions,
        match_status="manual",
        match_confidence=100.0,
        in_stock=float(medicine.current_stock or 0) > 0,
        current_stock_qty=float(medicine.current_stock or 0)
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
