"""
TrustChain endpoints (Pillar 4) - read-only ledger browsing plus the
owner-only full-chain verification check. Every actual ledger WRITE
happens inside the domain services themselves (rate_history subscriber,
expiry_service, stock_service - see each for its log_event() call); this
router never writes to audit_ledger, only reads through audit_service.

Kept owner-only, matching this codebase's existing convention for
financial/compliance-facing screens (routers/analytics.py, routers/gst.py).
"""
import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas
from app.services import audit_service
from app.deps import require_owner

router = APIRouter(prefix="/audit", dependencies=[Depends(require_owner)], tags=["audit"])


def _entry_to_out(entry) -> schemas.AuditLedgerEntryOut:
    return schemas.AuditLedgerEntryOut(
        id=entry.id,
        event_type=entry.event_type,
        reference_id=entry.reference_id,
        payload=json.loads(entry.payload_json),
        payload_hash=entry.payload_hash,
        previous_hash=entry.previous_hash,
        entry_hash=entry.entry_hash,
        created_at=entry.created_at,
    )


@router.get("/ledger", response_model=list[schemas.AuditLedgerEntryOut])
def get_ledger(
    event_type: str = Query(None, description="Filter to one event type, e.g. 'rate_change'"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Most recent ledger entries first - powers the TrustChain screen's main table."""
    entries = audit_service.get_ledger(db, event_type=event_type, limit=limit)
    return [_entry_to_out(e) for e in entries]


@router.get("/verify", response_model=schemas.AuditVerifyResult)
def verify_chain(db: Session = Depends(get_db)):
    """
    Walks the ENTIRE chain from genesis and recomputes every hash - proof
    that nothing in the audit trail has been altered since it was written,
    or an exact report of which entries broke and why if it has.
    """
    return audit_service.verify_chain(db)


@router.get("/for/{event_type}/{reference_id}", response_model=list[schemas.AuditLedgerEntryOut])
def get_entries_for_reference(event_type: str, reference_id: int, db: Session = Depends(get_db)):
    """e.g. every audit entry tied to one specific RateHistory row or StockLedger row."""
    entries = audit_service.get_entries_for_reference(db, event_type, reference_id)
    return [_entry_to_out(e) for e in entries]