"""
Tests for gst_report_service.py - the CGST/SGST math a CA actually relies
on, plus a sanity check that PDF generation produces a real, valid file.
"""
from datetime import datetime

from app.services import gst_report_service
from app import models


def _confirmed_bill_with_item(db_session, distributor, medicine, year, month, amount, gst_pct):
    bill = models.Bill(distributor_id=distributor.id, status="confirmed", year=year, month=month)
    db_session.add(bill)
    db_session.flush()
    item = models.BillItem(
        bill_id=bill.id, medicine_id=medicine.id, raw_name="TEST ITEM",
        qty=10, rate=amount / 10, gst_pct=gst_pct, amount=amount,
    )
    db_session.add(item)
    db_session.commit()
    return bill, item


def test_gst_math_splits_cgst_sgst_equally(db_session, sample_medicine, sample_distributor):
    # amount=1050 at 5% GST -> taxable=1000, total_tax=50, cgst=sgst=25
    _confirmed_bill_with_item(db_session, sample_distributor, sample_medicine, 2026, 7, 1050.0, 5.0)

    report = gst_report_service.get_gst_report(db_session, 2026, 7)

    assert report["bill_count"] == 1
    assert len(report["slabs"]) == 1
    slab = report["slabs"][0]
    assert slab["gst_pct"] == 5.0
    assert abs(slab["taxable_amount"] - 1000.0) < 0.5
    assert abs(slab["cgst"] - 25.0) < 0.5
    assert abs(slab["sgst"] - 25.0) < 0.5
    assert abs(slab["total_tax"] - 50.0) < 0.5
    assert abs(slab["total_amount"] - 1050.0) < 0.5


def test_only_confirmed_bills_are_counted(db_session, sample_medicine, sample_distributor):
    bill = models.Bill(distributor_id=sample_distributor.id, status="pending_review", year=2026, month=7)
    db_session.add(bill)
    db_session.flush()
    item = models.BillItem(
        bill_id=bill.id, medicine_id=sample_medicine.id, raw_name="X",
        qty=1, rate=100, gst_pct=5, amount=105.0,
    )
    db_session.add(item)
    db_session.commit()

    report = gst_report_service.get_gst_report(db_session, 2026, 7)
    assert report["bill_count"] == 0
    assert report["slabs"] == []


def test_multiple_gst_slabs_reported_separately(db_session, sample_medicine, sample_distributor):
    _confirmed_bill_with_item(db_session, sample_distributor, sample_medicine, 2026, 7, 1050.0, 5.0)
    _confirmed_bill_with_item(db_session, sample_distributor, sample_medicine, 2026, 7, 1120.0, 12.0)

    report = gst_report_service.get_gst_report(db_session, 2026, 7)
    gst_pcts = {s["gst_pct"] for s in report["slabs"]}
    assert gst_pcts == {5.0, 12.0}
    assert report["bill_count"] == 2


def test_wrong_month_returns_empty_report(db_session, sample_medicine, sample_distributor):
    _confirmed_bill_with_item(db_session, sample_distributor, sample_medicine, 2026, 7, 1050.0, 5.0)

    report = gst_report_service.get_gst_report(db_session, 2026, 8)  # different month
    assert report["bill_count"] == 0
    assert report["grand_total_amount"] == 0.0


def test_pdf_generation_produces_a_valid_pdf_file():
    report = {
        "year": 2026, "month": 7, "month_label": "July 2026",
        "slabs": [{
            "gst_pct": 5.0, "taxable_amount": 1000.0, "cgst": 25.0, "sgst": 25.0,
            "total_tax": 50.0, "total_amount": 1050.0, "item_count": 1,
        }],
        "grand_taxable_amount": 1000.0, "grand_cgst": 25.0, "grand_sgst": 25.0,
        "grand_total_tax": 50.0, "grand_total_amount": 1050.0, "bill_count": 1,
    }
    pdf_bytes = gst_report_service.generate_gst_report_pdf(report)

    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes[:4] == b"%PDF"   # real PDF file header
    assert len(pdf_bytes) > 500        # not an empty/broken document