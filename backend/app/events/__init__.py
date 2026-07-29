"""
Event-Driven Architecture (EDA) Package.
Exports core event models, EventBus singleton, and subscriber registration setup.
"""
from app.events.events import (
    DomainEvent,
    BillUploadedEvent,
    BillProcessedEvent,
    BillConfirmedEvent,
    StockUpdatedEvent,
    RateChangedEvent,
)
from app.events.bus import event_bus, EventBus
from app.events.subscribers import register_all_subscribers

__all__ = [
    "DomainEvent",
    "BillUploadedEvent",
    "BillProcessedEvent",
    "BillConfirmedEvent",
    "StockUpdatedEvent",
    "RateChangedEvent",
    "event_bus",
    "EventBus",
    "register_all_subscribers",
]
