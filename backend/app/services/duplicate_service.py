"""
Service module for duplicate invoice detection.
Confirm-time hard gate (prevents ledger double-counting).

This module is used at CONFIRM time (see routers/bills.py confirm_bill) as a strict 409
rejection gate. It checks ONLY against already-confirmed bills, using a normalized 
invoice number (stripping spaces/punctuation) to catch typos like "INV-123" vs "INV 123".

For the upload-time soft warning that checks file checksums and pending bills, 
see `duplicate_checker.py`. Both are necessary and serve different stages of the pipeline.
"""
import re
from typing import Optional
from sqlalchemy.orm import Session
from app import models


def normalize_invoice_no(invoice_no: Optional[str]) -> Optional[str]:
    """
    Trim whitespace and uppercase, so 'inv-123 ' and 'INV-123' are treated as the same invoice.
    Return None if the result is empty or input is None.
    """
    if not invoice_no:
        return None
    cleaned = invoice_no.strip().upper()
    return cleaned if cleaned else None


def find_confirmed_duplicate(
    db: Session,
    distributor_id: Optional[int],
    invoice_no: Optional[str],
    exclude_bill_id: Optional[int] = None,
) -> Optional[models.Bill]:
    """
    Returns the existing CONFIRMED Bill with the same distributor_id + normalized invoice_no,
    or None. Returns None immediately (does not query) if distributor_id is None or
    normalize_invoice_no(invoice_no) is None - a bill with no invoice number or no resolved
    distributor cannot be meaningfully deduplicated, and must never produce a false positive.
    """
    normalized_inv = normalize_invoice_no(invoice_no)
    if distributor_id is None or normalized_inv is None:
        return None

    query = db.query(models.Bill).filter(
        models.Bill.distributor_id == distributor_id,
        models.Bill.status == "confirmed",
    )

    if exclude_bill_id is not None:
        query = query.filter(models.Bill.id != exclude_bill_id)

    confirmed_bills = query.all()
    for bill in confirmed_bills:
        if normalize_invoice_no(bill.invoice_no) == normalized_inv:
            return bill

    return None
