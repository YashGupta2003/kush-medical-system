"""
Tests for gst_report_service.py - purchase GST math, period handling, IGST/inter-state,
undated separation/warnings, additive sales/output estimates, and PDF generation.
Issue 6: Decimal math and invoice_date-based perioding.
"""
from datetime import datetime, timezone
from decimal import Decimal

from app.services import gst_report_service, stock_service
from app import models


def _confirmed_bill_with_item(
    db_session, tenant, distributor, medicine, year, month, amount, gst_pct,
    invoice_date=None, status="confirmed",
):
    bill = models.Bill(
        tenant_id=tenant.id, distributor_id=distributor.id, status=status,
        year=year, month=month,
        invoice_date=invoice_date if invoice_date is not None else datetime(year, month, 15),
    )
    db_session.add(bill)
    db_session.flush()
    item = models.BillItem(
        bill_id=bill.id, medicine_id=medicine.id, raw_name="TEST ITEM",
        qty=10, rate=float(Decimal(str(amount)) / Decimal("10")), gst_pct=gst_pct, amount=amount,
    )
    db_session.add(item)
    db_session.commit()
    return bill, item


def test_gst_math_splits_cgst_sgst_equally_intra_state(db_session, tenant, sample_medicine, sample_distributor):
    # amount=1050 at 5% GST -> taxable=1000, total_tax=50, cgst=sgst=25
    _confirmed_bill_with_item(db_session, tenant, sample_distributor, sample_medicine, 2026, 7, 1050.0, 5.0)

    report = gst_report_service.get_gst_report(db_session, tenant.id, 2026, 7)

    assert report["bill_count"] == 1
    assert report["period_basis"] == "bill.invoice_date"
    assert len(report["slabs"]) == 1
    slab = report["slabs"][0]
    assert slab["gst_pct"] == 5.0
    assert slab["taxable_amount"] == 1000.0
    assert slab["cgst"] == 25.0
    assert slab["sgst"] == 25.0
    assert slab["igst"] == 0.0
    assert slab["total_tax"] == 50.0
    assert slab["total_amount"] == 1050.0
    assert report["grand_igst"] == 0.0


def test_only_confirmed_bills_are_counted(db_session, tenant, sample_medicine, sample_distributor):
    bill = models.Bill(
        tenant_id=tenant.id, distributor_id=sample_distributor.id, status="pending_review",
        year=2026, month=7, invoice_date=datetime(2026, 7, 10),
    )
    db_session.add(bill)
    db_session.flush()
    item = models.BillItem(
        bill_id=bill.id, medicine_id=sample_medicine.id, raw_name="X",
        qty=1, rate=100, gst_pct=5, amount=105.0,
    )
    db_session.add(item)
    db_session.commit()

    report = gst_report_service.get_gst_report(db_session, tenant.id, 2026, 7)
    assert report["bill_count"] == 0
    assert report["slabs"] == []


def test_multiple_gst_slabs_reported_separately(db_session, tenant, sample_medicine, sample_distributor):
    _confirmed_bill_with_item(db_session, tenant, sample_distributor, sample_medicine, 2026, 7, 1050.0, 5.0)
    _confirmed_bill_with_item(db_session, tenant, sample_distributor, sample_medicine, 2026, 7, 1120.0, 12.0)

    report = gst_report_service.get_gst_report(db_session, tenant.id, 2026, 7)
    gst_pcts = {s["gst_pct"] for s in report["slabs"]}
    assert gst_pcts == {5.0, 12.0}
    assert report["bill_count"] == 2


def test_period_uses_invoice_date_not_bill_year_month(db_session, tenant, sample_medicine, sample_distributor):
    # Bill.year/month says July but invoice_date is in August -> must count in August period.
    bill = models.Bill(
        tenant_id=tenant.id, distributor_id=sample_distributor.id, status="confirmed",
        year=2026, month=7, invoice_date=datetime(2026, 8, 5),
    )
    db_session.add(bill)
    db_session.flush()
    db_session.add(models.BillItem(
        bill_id=bill.id, medicine_id=sample_medicine.id, raw_name="X",
        qty=1, rate=100, gst_pct=5, amount=105.0,
    ))
    db_session.commit()

    july = gst_report_service.get_gst_report(db_session, tenant.id, 2026, 7)
    august = gst_report_service.get_gst_report(db_session, tenant.id, 2026, 8)
    assert july["bill_count"] == 0
    assert august["bill_count"] == 1
    assert august["grand_total_amount"] == 105.0


def test_undated_confirmed_bills_are_separated_with_warning(db_session, tenant, sample_medicine, sample_distributor):
    bill = models.Bill(
        tenant_id=tenant.id, distributor_id=sample_distributor.id, status="confirmed",
        year=2026, month=7, invoice_date=None,
    )
    db_session.add(bill)
    db_session.flush()
    db_session.add(models.BillItem(
        bill_id=bill.id, medicine_id=sample_medicine.id, raw_name="X",
        qty=1, rate=100, gst_pct=5, amount=105.0,
    ))
    db_session.commit()

    report = gst_report_service.get_gst_report(db_session, tenant.id, 2026, 7)
    assert report["bill_count"] == 0
    assert report["slabs"] == []
    assert report["undated_bill_count"] == 1
    assert bill.id in report["undated_bill_ids"]
    assert any("invoice_date" in w for w in report["warnings"])


def test_interstate_purchase_uses_igst_when_gstin_states_differ(db_session, tenant, sample_medicine):
    tenant.gstin = "27AAAAA0000A1Z5"
    inter_state_dist = models.Distributor(tenant_id=tenant.id, name="INTERSTATE DIST", gstin="29BBBBB0000B1Z5")
    db_session.add(inter_state_dist)
    db_session.commit()
    db_session.refresh(inter_state_dist)

    _confirmed_bill_with_item(db_session, tenant, inter_state_dist, sample_medicine, 2026, 7, 1050.0, 5.0)
    report = gst_report_service.get_gst_report(db_session, tenant.id, 2026, 7)

    slab = report["slabs"][0]
    assert slab["igst"] == 50.0
    assert slab["cgst"] == 0.0
    assert slab["sgst"] == 0.0
    assert report["grand_igst"] == 50.0
    assert report["assumed_intrastate_bill_count"] == 0


def test_sales_output_estimates_included_from_sale_snapshots(db_session, tenant, sample_medicine, sample_distributor, owner_user):
    # A confirmed purchase in period (to keep report valid) and a sale in same period
    _confirmed_bill_with_item(db_session, tenant, sample_distributor, sample_medicine, 2026, 7, 1050.0, 5.0)
    # ensure medicine has pricing and stock
    sample_medicine.mrp = Decimal("100.00")
    sample_medicine.net_rate = Decimal("60.00")
    sample_medicine.current_stock = Decimal("10")
    db_session.commit()

    stock_service.record_sale(db_session, tenant.id, sample_medicine.id, qty_sold=1, created_by_user_id=owner_user.id, commit=True)
    # Ensure sale sold_at falls in 2026-07 for this test context by adjusting if needed
    sale = db_session.query(models.Sale).order_by(models.Sale.id.desc()).first()
    sale.sold_at = datetime(2026, 7, 20, tzinfo=timezone.utc)
    db_session.commit()

    report = gst_report_service.get_gst_report(db_session, tenant.id, 2026, 7)
    so = report.get("sales_output_estimates")
    assert so is not None
    assert so["sale_count"] >= 1
    assert so["grand_total_amount"] > 0
    assert "slabs" in so


def test_pdf_generation_produces_a_valid_pdf_file():
    report = {
        "year": 2026, "month": 7, "month_label": "July 2026",
        "period_basis": "bill.invoice_date",
        "slabs": [{
            "gst_pct": 5.0, "taxable_amount": 1000.0, "cgst": 25.0, "sgst": 25.0, "igst": 0.0,
            "total_tax": 50.0, "total_amount": 1050.0, "item_count": 1,
        }],
        "grand_taxable_amount": 1000.0, "grand_cgst": 25.0, "grand_sgst": 25.0, "grand_igst": 0.0,
        "grand_total_tax": 50.0, "grand_total_amount": 1050.0, "bill_count": 1,
        "undated_bill_count": 0, "undated_bill_ids": [], "assumed_intrastate_bill_count": 0,
        "warnings": [],
        "sales_output_estimates": {"period_basis": "sale.sold_at", "slabs": [], "sale_count": 0,
                                   "grand_taxable_amount": 0.0, "grand_cgst": 0.0, "grand_sgst": 0.0,
                                   "grand_igst": 0.0, "grand_total_tax": 0.0, "grand_total_amount": 0.0, "note": ""},
    }
    pdf_bytes = gst_report_service.generate_gst_report_pdf(report)

    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes[:4] == b"%PDF"   # real PDF file header
    assert len(pdf_bytes) > 500        # not an empty/broken document
