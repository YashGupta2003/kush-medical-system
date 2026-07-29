"""
Domain Events definition for Event-Driven Architecture.
All events are immutable data structures describing significant business domain actions.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session


@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    """Base class for all domain events."""
    timestamp: datetime = field(default_factory=datetime.utcnow)


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
