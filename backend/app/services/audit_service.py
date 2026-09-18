"""
TrustChain — Tamper-Evident Audit Trail (Pillar 4, deliberately scoped).

Design note (matches pharma_roadmap.md's reasoning exactly): a single
shop's database has ONE trust boundary — you trust your own MySQL
instance. A distributed blockchain solves "how do mutually-untrusting
parties agree on shared history without a central authority" — that isn't
this system's problem, so pretending it needs Hyperledger/a distributed
ledger for one shop's own audit trail would be a buzzword bolt-on, not
real engineering. Real blockchain only becomes justified once Pillar 5's
inter-pharmacy network exists and multiple independent shop owners who
do NOT inherently trust each other start transacting stock between
themselves — that's a genuine multi-party trust problem this system
doesn't have yet.

What THIS system needs, and what this module provides, is tamper-EVIDENCE:
proof that nobody — not even someone with direct DB access, bypassing the
app entirely — silently edited a past rate change, stock adjustment, or
confirmed bill's numbers without it being detectable. A hash chain gives
you exactly that, with none of a distributed ledger's complexity:

    entry_hash[n] = SHA256(payload_hash[n] + entry_hash[n-1])

Every entry's hash depends on the entry before it, all the way back to a
fixed genesis value. Edit ANY past entry's payload and its payload_hash
changes, which changes its entry_hash, which no longer matches what the
NEXT entry recorded as its previous_hash — the mismatch cascades forward
through every entry after it. Detecting tampering is just walking the
chain and recomputing every hash from scratch (see verify_chain below).

This module is the ONLY place that writes to audit_ledger — every event
that should be tamper-logged calls log_event() here, the same
single-writer convention this codebase already uses for graph_edges (see
graph_service.py).
"""
import hashlib
import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import asc

from app import models

# Fixed starting point for the very first entry in the chain - an entry
# whose previous_hash is anything OTHER than this is either not the first
# entry, or has had an earlier entry deleted out from under it.
GENESIS_HASH = "0" * 64


def _canonical_json(payload: dict) -> str:
    """
    Deterministic JSON serialization - sorted keys, no incidental
    whitespace differences - so the exact same logical payload always
    hashes to the exact same value regardless of dict insertion order.
    default=str handles datetime/Decimal values without extra caller-side
    conversion.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_last_entry(db: Session) -> Optional[models.AuditLedgerEntry]:
    return (
        db.query(models.AuditLedgerEntry)
        .order_by(models.AuditLedgerEntry.id.desc())
        .first()
    )


def log_event(db: Session, event_type: str, reference_id: Optional[int], payload: dict) -> models.AuditLedgerEntry:
    """
    Appends one tamper-evident entry to the end of the chain.

    Safe to call from inside an already-open transaction - uses flush, not
    commit, so an audit entry always succeeds or fails together with
    whatever business write it's documenting (e.g. a RateHistory row and
    its audit entry are never left half-written relative to each other).

    Concurrency note: previous_hash is read via get_last_entry() just
    before this entry is built. Under FastAPI's one-session-per-request
    model with MySQL's default transaction isolation, two truly
    simultaneous confirms could theoretically both read the same "last"
    entry - for a single-shop system with a handful of staff accounts this
    is an accepted, documented limitation (not a silent correctness bug -
    verify_chain would immediately surface it as a broken previous_hash
    link if it ever happened), not something a student project needs a
    distributed consensus algorithm to solve.
    """
    canonical = _canonical_json(payload)
    payload_hash = _sha256(canonical)

    last = get_last_entry(db)
    previous_hash = last.entry_hash if last else GENESIS_HASH

    entry_hash = _sha256(payload_hash + previous_hash)

    entry = models.AuditLedgerEntry(
        tenant_id=payload.get("tenant_id"),
        event_type=event_type,
        reference_id=reference_id,
        payload_json=canonical,
        payload_hash=payload_hash,
        previous_hash=previous_hash,
        entry_hash=entry_hash,
        created_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    db.flush()
    return entry


def verify_chain(db: Session) -> dict:
    """
    Walks the FULL chain oldest-first and recomputes every hash from
    scratch, comparing against what's actually stored. Returns a report
    the Owner can act on, not a bare true/false - WHICH entry broke, and
    exactly why, is what makes this actionable during an investigation
    rather than just an alarm bell.

    Three independent things are checked per entry:
      1. payload_hash still matches payload_json  -> the payload itself
         wasn't edited directly in the DB.
      2. previous_hash matches the prior entry's actual entry_hash -> no
         entry was inserted, deleted, or reordered in the chain.
      3. entry_hash matches SHA256(payload_hash + previous_hash) -> the
         entry_hash field itself wasn't edited directly.

    The walk continues past a broken entry using what's ACTUALLY stored
    as that entry's hash (not what it "should" have been) - this is what
    lets a single early tamper be reported precisely, instead of every
    single later entry also showing up as "broken" once the chain has
    already diverged from expectation.
    """
    entries = (
        db.query(models.AuditLedgerEntry)
        .order_by(asc(models.AuditLedgerEntry.id))
        .all()
    )

    broken_at: list[dict] = []
    expected_previous = GENESIS_HASH

    for entry in entries:
        recomputed_payload_hash = _sha256(entry.payload_json)
        recomputed_entry_hash = _sha256(recomputed_payload_hash + expected_previous)

        problems = []
        if recomputed_payload_hash != entry.payload_hash:
            problems.append("Payload does not match its stored hash — this entry's data was edited directly in the database.")
        if entry.previous_hash != expected_previous:
            problems.append("This entry's previous_hash does not match the prior entry's actual hash — an entry was inserted, deleted, or reordered.")
        if recomputed_entry_hash != entry.entry_hash:
            problems.append("This entry's own hash does not match its payload + previous hash — the entry_hash field was edited directly.")

        if problems:
            broken_at.append({
                "id": entry.id,
                "event_type": entry.event_type,
                "reference_id": entry.reference_id,
                "created_at": entry.created_at.isoformat() if entry.created_at else None,
                "problems": problems,
            })

        expected_previous = entry.entry_hash

    return {
        "total_entries": len(entries),
        "is_valid": len(broken_at) == 0,
        "broken_entries": broken_at,
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }


def get_ledger_paginated(db: Session, event_type: Optional[str] = None, limit: int = 100, offset: int = 0) -> tuple[list[models.AuditLedgerEntry], int]:
    """Most recent entries first - what the TrustChain screen's main table shows, with total count."""
    q = db.query(models.AuditLedgerEntry)
    if event_type:
        q = q.filter(models.AuditLedgerEntry.event_type == event_type)
    total = q.count()
    items = q.order_by(models.AuditLedgerEntry.id.desc()).offset(offset).limit(limit).all()
    return items, total


def get_entries_for_reference(db: Session, event_type: str, reference_id: int) -> list[models.AuditLedgerEntry]:
    """
    e.g. every rate_change entry for one specific RateHistory row, or every
    stock_adjustment entry tied to one StockLedger row - oldest first, so
    it reads as a timeline.
    """
    return (
        db.query(models.AuditLedgerEntry)
        .filter(models.AuditLedgerEntry.event_type == event_type, models.AuditLedgerEntry.reference_id == reference_id)
        .order_by(models.AuditLedgerEntry.id.asc())
        .all()
    )