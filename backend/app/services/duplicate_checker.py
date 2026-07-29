"""
Duplicate Bill Protection Service.
Prevents uploading or confirming duplicate invoices, protecting stock and GST ledgers
from double counting.
"""
import hashlib
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app import models
from app.core.logging import get_logger

logger = get_logger("duplicate_checker")


def compute_file_checksum(file_bytes: bytes) -> str:
    """Computes SHA-256 checksum for given file bytes."""
    return hashlib.sha256(file_bytes).hexdigest()


def check_duplicate_bill(
    db: Session,
    file_bytes: Optional[bytes] = None,
    invoice_no: Optional[str] = None,
    distributor_id: Optional[int] = None,
) -> Tuple[bool, Optional[str], Optional[models.Bill]]:
    """
    Checks if a bill with identical checksum or matching (distributor_id, invoice_no) exists.
    Returns: (is_duplicate: bool, reason: str, existing_bill: Bill)
    """
    # 1. Check exact image checksum if provided
    if file_bytes:
        checksum = compute_file_checksum(file_bytes)
        existing_by_hash = db.query(models.Bill).filter(models.Bill.checksum == checksum).first()
        if existing_by_hash:
            msg = f"Duplicate bill image detected (matches Bill #{existing_by_hash.id}, status: {existing_by_hash.status})"
            logger.warning(msg)
            return True, msg, existing_by_hash

    # 2. Check invoice_no + distributor_id combination
    if invoice_no and distributor_id:
        existing_by_inv = (
            db.query(models.Bill)
            .filter(
                models.Bill.distributor_id == distributor_id,
                models.Bill.invoice_no == invoice_no.strip(),
                models.Bill.status.in_(["pending_review", "needs_attention", "confirmed"])
            )
            .first()
        )
        if existing_by_inv:
            msg = f"Bill with invoice number '{invoice_no}' already exists for this distributor (Bill #{existing_by_inv.id}, status: {existing_by_inv.status})"
            logger.warning(msg)
            return True, msg, existing_by_inv

    return False, None, None
