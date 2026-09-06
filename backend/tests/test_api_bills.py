"""
API-level tests for /bills router, covering confirm flow happy path,
duplicate warning at upload, HTTP 409 conflict at confirm, and invoice_no correction.
"""
import io
import pytest
from app import models


def test_confirm_bill_happy_path(client, staff_headers, sample_medicine, sample_distributor, db_session, tenant):
    # 1. Create a bill in pending_review status
    bill = models.Bill(
        tenant_id=tenant.id,
        distributor_id=sample_distributor.id,
        invoice_no="INV-5001",
        status="pending_review",
        month=7,
        year=2026,
    )
    db_session.add(bill)
    db_session.commit()

    item = models.BillItem(
        bill_id=bill.id,
        raw_name="AMLOKIND AT TAB",
        qty=10,
        free_qty=2,
        rate=50.0,
        mrp=100.0,
        discount_pct=10.0,
        gst_pct=12.0,
        medicine_id=sample_medicine.id,
        match_status="auto",
    )
    db_session.add(item)
    db_session.commit()

    # 2. Confirm the bill via POST /bills/confirm
    payload = {
        "bill_id": bill.id,
        "items": [
            {
                "id": item.id,
                "raw_name": "AMLOKIND AT TAB",
                "qty": 10,
                "free_qty": 2,
                "mrp": 100.0,
                "rate": 50.0,
                "discount_pct": 10.0,
                "special_discount_pct": 0,
                "gst_pct": 12.0,
                "medicine_id": sample_medicine.id,
                "apply_to_master_list": True,
            }
        ]
    }
    resp = client.post("/bills/confirm", json=payload, headers=staff_headers)
    assert resp.status_code == 200

    db_session.refresh(bill)
    db_session.refresh(sample_medicine)
    assert bill.status == "confirmed"
    # Stock updated: original stock 20 + 10 + 2 = 32
    assert float(sample_medicine.current_stock) == 32.0


def test_duplicate_warning_at_upload_and_409_at_confirm(client, staff_headers, sample_distributor, db_session, tenant):
    # Existing CONFIRMED bill with same distributor and invoice_no
    bill1 = models.Bill(
        tenant_id=tenant.id,
        distributor_id=sample_distributor.id,
        invoice_no="INV-9999",
        status="confirmed",
    )
    db_session.add(bill1)
    db_session.commit()

    # Upload a new bill with same distributor and invoice_no
    file_content = b"fake image bytes for test"
    files = {"file": ("test_invoice.jpg", io.BytesIO(file_content), "image/jpeg")}
    data = {
        "distributor_name": sample_distributor.name,
        "invoice_no": "inv-9999 ",  # case & whitespace difference
    }

    upload_resp = client.post("/bills/upload", files=files, data=data, headers=staff_headers)
    assert upload_resp.status_code == 200
    res_json = upload_resp.json()
    assert res_json["duplicate_warning"] is not None
    assert "already confirmed" in res_json["duplicate_warning"]

    new_bill_id = res_json["bill_id"]

    # Attempting to confirm the duplicate bill returns HTTP 409 Conflict
    confirm_payload = {
        "bill_id": new_bill_id,
        "items": [],
    }
    confirm_resp = client.post("/bills/confirm", json=confirm_payload, headers=staff_headers)
    assert confirm_resp.status_code == 409
    assert "already confirmed" in confirm_resp.json()["detail"]

    # Correcting the invoice number to a unique value lets confirm succeed
    correct_payload = {
        "bill_id": new_bill_id,
        "invoice_no": "INV-9999-PART2",
        "items": [],
    }
    confirm_resp_2 = client.post("/bills/confirm", json=correct_payload, headers=staff_headers)
    assert confirm_resp_2.status_code == 200

    new_bill = db_session.query(models.Bill).get(new_bill_id)
    assert new_bill.status == "confirmed"
    assert new_bill.invoice_no == "INV-9999-PART2"
