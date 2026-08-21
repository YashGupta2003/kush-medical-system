"""
Domain Events definition for Event-Driven Architecture.
All events are immutable data structures describing significant business domain actions.

Priority 1 additions (Notification Engine):
  - AdherenceAlertRaisedEvent  — fired by Celery adherence scan task
  - AnomalyFlaggedEvent        — fired by Celery anomaly scan task
  - LowStockCrossedEvent       — fired from stock_service._add_ledger_entry
  - CreditOverdueEvent         — fired by Celery credit overdue scan task
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session


@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    """Base class for all domain events."""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True, kw_only=True)
class BillUploadedEvent(DomainEvent):
    """Fired when a new bill image is uploaded and queued for processing."""
    bill_id: int
    filename: str
    distributor_name: Optional[str] = None
    checksum: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class BillProcessedEvent(DomainEvent):
    """Fired when background OCR & parsing completes for a bill."""
    bill_id: int
    status: str
    ocr_confidence: float
    items_count: int


@dataclass(frozen=True, kw_only=True)
class BillConfirmedEvent(DomainEvent):
    """
    Fired when a user confirms a bill on the review screen.
    Triggers downstream pipelines: stock addition, batch/expiry creation,
    rate history auditing, master rate updates, learned mapping, and cache invalidation.
    """
    bill_id: int
    db: Session
    items_edits: List[Any]
    distributor_id: Optional[int] = None


@dataclass(frozen=True, kw_only=True)
class StockUpdatedEvent(DomainEvent):
    """Fired whenever physical stock is changed."""
    medicine_id: int
    change_qty: float
    resulting_balance: float
    reason: str
    bill_item_id: Optional[int] = None


@dataclass(frozen=True, kw_only=True)
class RateChangedEvent(DomainEvent):
    """Fired whenever a medicine's rate or MRP is updated from a bill."""
    medicine_id: int
    old_net_rate: Optional[float]
    new_net_rate: Optional[float]
    old_mrp: Optional[float]
    new_mrp: Optional[float]
    bill_item_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Priority 1 — Notification Engine events
# ---------------------------------------------------------------------------

@dataclass(frozen=True, kw_only=True)
class LowStockCrossedEvent(DomainEvent):
    """
    Fired by stock_service._add_ledger_entry ONLY when a medicine's stock
    crosses BELOW its low_stock_threshold as a result of that ledger entry.

    The "crossing" logic (old_balance >= threshold AND new_balance < threshold)
    means this fires exactly once at the moment of crossing, not on every
    subsequent sale while already below threshold — preventing alert spam.

    db is included so the subscriber can write the Notification row in the
    same transaction as the ledger entry, matching the BillConfirmedEvent
    pattern where db is passed through to avoid a new session per event.
    """
    medicine_id: int
    medicine_name: str
    old_balance: float
    new_balance: float
    threshold: float
    db: Session


@dataclass(frozen=True, kw_only=True)
class AdherenceAlertRaisedEvent(DomainEvent):
    """
    Fired by the Celery adherence scan task for each overdue
    (customer, medicine) pair that hasn't been notified in the last 7 days.
    db is included for the subscriber to write the Notification row.
    """
    customer_id: int
    customer_name: Optional[str]
    customer_phone: str
    medicine_id: int
    medicine_name: str
    days_overdue: float
    avg_gap_days: float
    db: Session


@dataclass(frozen=True, kw_only=True)
class AnomalyFlaggedEvent(DomainEvent):
    """
    Fired by the Celery anomaly scan task when a price jump or stock
    adjustment anomaly is newly detected (not already notified today).
    """
    anomaly_type: str      # "price_jump" | "stock_adjustment"
    medicine_id: int
    medicine_name: str
    score: float
    detail: Dict[str, Any]
    db: Session


@dataclass(frozen=True, kw_only=True)
class CreditOverdueEvent(DomainEvent):
    """
    Fired by the Celery daily digest task for customers with a positive
    outstanding credit balance that hasn't been paid in a configurable
    number of days (currently: any outstanding balance, checked weekly).
    """
    customer_id: int
    customer_name: Optional[str]
    customer_phone: str
    outstanding_amount: float
    db: Session

@dataclass(frozen=True, kw_only=True)
class ColdChainExcursionEvent(DomainEvent):
    """Fired when a cold-chain reading falls outside the unit's safe range."""
    unit_id: int
    unit_label: str
    recorded_temp_c: float
    min_temp_c: float
    max_temp_c: float
    reading_id: int
    db: Session

@dataclass(frozen=True, kw_only=True)
class SurveillanceSpikeDetectedEvent(DomainEvent):
    """Fired when the daily surveillance scan detects a condition spike."""
    condition_name: str
    spike_date: str  # ISO date string
    count: int
    z_score: float
    avg_count: float
    db: Session


@dataclass(frozen=True, kw_only=True)
class DistributorTrustScoreDroppedEvent(DomainEvent):
    """Fired when a distributor's composite trust score drops below HIGH_RISK_THRESHOLD (40)."""
    distributor_id: int
    distributor_name: str
    old_score: float
    new_score: float
    reasons: list[str]
    db: Session
