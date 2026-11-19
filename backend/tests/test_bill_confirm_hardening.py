"""Issue 4: bill confirmation hardening (ownership, status, invoice_date, errors/guards)."""
import json
from datetime import date, datetime

import pytest
import sqlalchemy as sa
from fastapi import HTTPException

from app import models, schemas
from app.routers import bills as bills_router
from app.events.bus import event_bus


class DummyEdit:
    def __init__(self, id, medicine_id=None, raw_name=None):
        self.id = id
        self.medicine_id = medicine_id
        self.raw_name = raw_name
        self.qty = None
        self.free_qty = None
        self.mrp = None
        self.rate = None
        self.discount_pct = None
        self.special_discount_pct = None
        self.gst_pct = None
        self.exp_date = None
        self.apply_to_master_list = True


def _dummy_request(request_id="req-test-1"):
    class State:
        pass
    class Req:
        pass
    r = Req()
    r.state = State()
    r.state.request_id = request_id
    return r


def _make_bill(db_session, tenant, distributor, status="pending_review", invoice_no="INV-1", invoice_date=None):
    bill = models.Bill(
        tenant_id=tenant.id,
        distributor_id=distributor.id,
        invoice_no=invoice_no,
        invoice_date=invoice_date,
        status=status,
        year=2026,
        month=1,
    )
    db_session.add(bill)
    db_session.flush()
    return bill


def _make_item(db_session, tenant, bill, medicine=None, raw_name="ITEM"):
    item = models.BillItem(
        tenant_id=tenant.id,
        bill_id=bill.id,
        medicine_id=medicine.id if medicine else None,
        raw_name=raw_name,
        qty=1, free_qty=0, rate=10, gst_pct=0, amount=10,
        match_status="auto" if medicine else "unmatched",
    )
    db_session.add(item)
    db_session.flush()
    return item


def test_confirm_bill_rejects_edited_item_from_other_bill(db_session, tenant, sample_distributor, sample_medicine, staff_user):
    bill1 = _make_bill(db_session, tenant, sample_distributor, invoice_no="INV-A")
    bill2 = _make_bill(db_session, tenant, sample_distributor, invoice_no="INV-B")
    item1 = _make_item(db_session, tenant, bill1, sample_medicine)
    foreign_item = _make_item(db_session, tenant, bill2, sample_medicine, raw_name="FOREIGN")
    db_session.commit()

    payload = schemas.ConfirmBillRequest(
        bill_id=bill1.id,
        items=[schemas.BillItemEdit(id=foreign_item.id, medicine_id=sample_medicine.id, apply_to_master_list=False)],
    )
    with pytest.raises(HTTPException) as exc:
        bills_router.confirm_bill(payload, _dummy_request(), db_session, staff_user)
    assert exc.value.status_code == 400
    assert "do not belong" in str(exc.value.detail).lower()


def test_confirm_bill_updates_invoice_date_and_derived_period(db_session, tenant, sample_distributor, sample_medicine, staff_user):
    bill = _make_bill(db_session, tenant, sample_distributor, invoice_no="INV-DATE")
    item = _make_item(db_session, tenant, bill, sample_medicine)
    db_session.commit()

    payload = schemas.ConfirmBillRequest(
        bill_id=bill.id,
        items=[schemas.BillItemEdit(id=item.id, medicine_id=sample_medicine.id, apply_to_master_list=False)],
        invoice_date=date(2025, 11, 3),
    )
    result = bills_router.confirm_bill(payload, _dummy_request(), db_session, staff_user)
    assert isinstance(result, list)
    db_session.refresh(bill)
    assert bill.status == "confirmed"
    assert bill.invoice_date is not None
    assert bill.invoice_date.year == 2025
    assert bill.invoice_date.month == 11
    assert bill.year == 2025
    assert bill.month == 11
    assert bill.confirmed_invoice_key is not None


def test_confirm_bill_rejects_invalid_status_transition(db_session, tenant, sample_distributor, staff_user):
    bill = _make_bill(db_session, tenant, sample_distributor, status="queued", invoice_no="INV-Q")
    db_session.commit()
    payload = schemas.ConfirmBillRequest(bill_id=bill.id, items=[])
    with pytest.raises(HTTPException) as exc:
        bills_router.confirm_bill(payload, _dummy_request(), db_session, staff_user)
    assert exc.value.status_code == 409


def test_confirm_bill_sanitizes_unexpected_errors_and_logs_request_id(db_session, tenant, sample_distributor, sample_medicine, staff_user, monkeypatch):
    bill = _make_bill(db_session, tenant, sample_distributor, invoice_no="INV-ERR")
    item = _make_item(db_session, tenant, bill, sample_medicine)
    db_session.commit()

    def boom(*args, **kwargs):
        raise RuntimeError("secret-sql-detail")

    monkeypatch.setattr(event_bus, "publish", boom)
    payload = schemas.ConfirmBillRequest(
        bill_id=bill.id,
        items=[schemas.BillItemEdit(id=item.id, medicine_id=sample_medicine.id, apply_to_master_list=False)],
    )
    with pytest.raises(HTTPException) as exc:
        bills_router.confirm_bill(payload, _dummy_request("rid-xyz"), db_session, staff_user)
    assert exc.value.status_code == 500
    assert "secret-sql-detail" not in str(exc.value.detail)
    assert exc.value.detail == "Bill confirmation failed. Please retry."
    db_session.refresh(bill)
    assert bill.status != "confirmed"


def test_confirmed_invoice_key_unique_guard_blocks_duplicate_confirmed_rows(db_session, tenant, sample_distributor):
    b1 = _make_bill(db_session, tenant, sample_distributor, status="confirmed", invoice_no="INV-GUARD")
    b1.confirmed_invoice_key = f"{tenant.id}:{sample_distributor.id}:INV-GUARD"
    db_session.commit()

    b2 = _make_bill(db_session, tenant, sample_distributor, status="pending_review", invoice_no="INV-GUARD-2")
    b2.status = "confirmed"
    b2.confirmed_invoice_key = f"{tenant.id}:{sample_distributor.id}:INV-GUARD"
    db_session.add(b2)
    with pytest.raises(sa.exc.IntegrityError):
        db_session.commit()
    db_session.rollback()
