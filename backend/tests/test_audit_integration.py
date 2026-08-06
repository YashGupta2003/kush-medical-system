"""
Integration tests: confirms TrustChain (Pillar 4) is actually wired into
the existing event-driven pipeline - not just correct in isolation (see
test_audit_service.py for the hash-chain unit tests). These tests exercise
the real BillConfirmedEvent -> subscribers -> audit_service.log_event path,
and stock_service.record_adjustment's audit hook, the same way a real bill
confirmation or manual stock correction would.
"""
from app import models
from app.services import audit_service, stock_service
from app.events.bus import event_bus
from app.events.events import BillConfirmedEvent


def _pending_bill_with_item(db_session, medicine, distributor):
    bill = models.Bill(
        distributor_id=distributor.id, invoice_no="INV-AUDIT-1",
        status="pending_review", year=2026, month=8,
    )
    db_session.add(bill)
    db_session.commit()

    item = models.BillItem(
        bill_id=bill.id, raw_name=medicine.particulars, medicine_id=medicine.id,
        qty=10, free_qty=0, rate=50.0, mrp=100.0, discount_pct=0, gst_pct=12.0,
        match_status="auto",
    )
    db_session.add(item)
    db_session.commit()
    return bill, item


class DummyEdit:
    """Mimics schemas.BillItemEdit's shape without the pydantic overhead."""
    def __init__(self, id, medicine_id, rate=50.0, qty=10, mrp=100.0, gst_pct=12.0, exp_date="6/28"):
        self.id = id
        self.medicine_id = medicine_id
        self.raw_name = None
        self.qty = qty
        self.free_qty = 0
        self.mrp = mrp
        self.rate = rate
        self.discount_pct = 0
        self.special_discount_pct = 0
        self.gst_pct = gst_pct
        self.exp_date = exp_date
        self.apply_to_master_list = True


def test_confirming_a_bill_creates_rate_change_and_bill_confirmed_audit_entries(db_session, sample_medicine, sample_distributor):
    bill, item = _pending_bill_with_item(db_session, sample_medicine, sample_distributor)
    edit = DummyEdit(id=item.id, medicine_id=sample_medicine.id)

    event = BillConfirmedEvent(bill_id=bill.id, db=db_session, items_edits=[edit], distributor_id=bill.distributor_id)
    object.__setattr__(event, "changes_output", [])
    event_bus.publish(event)
    db_session.commit()

    rate_change_entries = audit_service.get_ledger(db_session, event_type="rate_change")
    bill_confirmed_entries = audit_service.get_ledger(db_session, event_type="bill_confirmed")
    batch_received_entries = audit_service.get_ledger(db_session, event_type="batch_received")

    assert len(rate_change_entries) == 1
    assert rate_change_entries[0].payload_json  # non-empty, valid JSON string
    assert len(bill_confirmed_entries) == 1
    assert len(batch_received_entries) == 1

    # The full chain (across all three entry types together) must still verify clean.
    report = audit_service.verify_chain(db_session)
    assert report["is_valid"] is True
    assert report["total_entries"] == 3


def test_bill_confirmed_entry_reflects_the_actual_bill(db_session, sample_medicine, sample_distributor):
    bill, item = _pending_bill_with_item(db_session, sample_medicine, sample_distributor)
    bill.total_amount = 550.0
    db_session.commit()
    edit = DummyEdit(id=item.id, medicine_id=sample_medicine.id)

    event = BillConfirmedEvent(bill_id=bill.id, db=db_session, items_edits=[edit], distributor_id=bill.distributor_id)
    object.__setattr__(event, "changes_output", [])
    event_bus.publish(event)
    db_session.commit()

    import json
    entries = audit_service.get_entries_for_reference(db_session, "bill_confirmed", bill.id)
    assert len(entries) == 1
    payload = json.loads(entries[0].payload_json)
    assert payload["bill_id"] == bill.id
    assert payload["invoice_no"] == "INV-AUDIT-1"
    assert payload["total_amount"] == 550.0


def test_manual_stock_adjustment_creates_audit_entry(db_session, sample_medicine):
    initial = float(sample_medicine.current_stock)

    stock_service.record_adjustment(db_session, sample_medicine.id, initial + 25, note="Physical count correction")

    entries = audit_service.get_ledger(db_session, event_type="stock_adjustment")
    assert len(entries) == 1

    import json
    payload = json.loads(entries[0].payload_json)
    assert payload["medicine_id"] == sample_medicine.id
    assert payload["previous_stock"] == initial
    assert payload["new_stock"] == initial + 25
    assert payload["note"] == "Physical count correction"

    report = audit_service.verify_chain(db_session)
    assert report["is_valid"] is True


def test_two_confirmed_bills_chain_together_in_upload_order(db_session, sample_medicine, sample_distributor):
    """
    A second bill's rate_change entry must chain from wherever the first
    bill's LAST audit entry left off - not start its own independent
    chain. This is what makes the whole ledger one continuous, globally
    verifiable history instead of per-bill islands.
    """
    bill1, item1 = _pending_bill_with_item(db_session, sample_medicine, sample_distributor)
    event1 = BillConfirmedEvent(bill_id=bill1.id, db=db_session, items_edits=[DummyEdit(id=item1.id, medicine_id=sample_medicine.id, rate=55.0)], distributor_id=bill1.distributor_id)
    object.__setattr__(event1, "changes_output", [])
    event_bus.publish(event1)
    db_session.commit()

    last_before_second_bill = audit_service.get_last_entry(db_session)

    bill2 = models.Bill(distributor_id=sample_distributor.id, invoice_no="INV-AUDIT-2", status="pending_review", year=2026, month=8)
    db_session.add(bill2)
    db_session.commit()
    item2 = models.BillItem(
        bill_id=bill2.id, raw_name=sample_medicine.particulars, medicine_id=sample_medicine.id,
        qty=5, free_qty=0, rate=60.0, mrp=110.0, discount_pct=0, gst_pct=12.0, match_status="auto",
    )
    db_session.add(item2)
    db_session.commit()

    event2 = BillConfirmedEvent(bill_id=bill2.id, db=db_session, items_edits=[DummyEdit(id=item2.id, medicine_id=sample_medicine.id, rate=60.0)], distributor_id=bill2.distributor_id)
    object.__setattr__(event2, "changes_output", [])
    event_bus.publish(event2)
    db_session.commit()

    first_entry_of_second_bill = (
        db_session.query(models.AuditLedgerEntry)
        .filter(models.AuditLedgerEntry.id > last_before_second_bill.id)
        .order_by(models.AuditLedgerEntry.id.asc())
        .first()
    )
    assert first_entry_of_second_bill.previous_hash == last_before_second_bill.entry_hash

    report = audit_service.verify_chain(db_session)
    assert report["is_valid"] is True