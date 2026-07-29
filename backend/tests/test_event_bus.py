"""
Unit tests for Event-Driven Architecture (EventBus, Domain Events, and Subscribers).
"""
import pytest
from unittest.mock import MagicMock
from app.events.bus import EventBus
from app.events.events import DomainEvent, BillUploadedEvent, BillConfirmedEvent
from app.events.subscribers import handle_bill_uploaded_logging


def test_event_bus_register_and_publish():
    bus = EventBus()
    received_events = []

    def mock_handler(event: DomainEvent):
        received_events.append(event)

    bus.subscribe(BillUploadedEvent, mock_handler)
    event = BillUploadedEvent(bill_id=101, filename="test_invoice.jpg", distributor_name="RATHORE MEDICOS")

    bus.publish(event)

    assert len(received_events) == 1
    assert received_events[0].bill_id == 101
    assert received_events[0].filename == "test_invoice.jpg"


def test_event_bus_exception_isolation():
    bus = EventBus()
    good_handler_executed = []

    def failing_handler(event: DomainEvent):
        raise ValueError("Simulated subscriber error")

    def good_handler(event: DomainEvent):
        good_handler_executed.append(True)

    bus.subscribe(BillUploadedEvent, failing_handler)
    bus.subscribe(BillUploadedEvent, good_handler)

    event = BillUploadedEvent(bill_id=102, filename="invoice_2.jpg")
    # Publishing should catch subscriber error and continue executing remaining subscribers
    bus.publish(event)

    assert len(good_handler_executed) == 1
