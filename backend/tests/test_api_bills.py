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
    file_content = bytes.fromhex('FFD8FFE000104A46494600010100000100010000FFDB004300080606070605080707070909080A0C140D0C0B0B0C1912130F141D1A1F1E1D1A1C1C20242E2720222C231C1C2837292C30313434341F27393D38323C2E333432FFDB0043010909090C0B0C180D0D1832211C213232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232FFC0000B080001000103012200021101031101FFC4001F0000010501010101010100000000000000000102030405060708090A0BFFC400B5100002010303020403050504040000017D01020300041105122131410613516107227114328191A1082342B1C11552D1F02433627282090A161718191A25262728292A3435363738393A434445464748494A535455565758595A636465666768696A737475767778797A838485868788898A92939495969798999AA2A3A4A5A6A7A8A9AAB2B3B4B5B6B7B8B9BAC2C3C4C5C6C7C8C9CAD2D3D4D5D6D7D8D9DAE1E2E3E4E5E6E7E8E9EAF1F2F3F4F5F6F7F8F9FAFFC4001F0100030101010101010101010000000000000102030405060708090A0BFFC400B5110002010204040304070504040001021100030104122131051341516106142271813291A1152342B1C1D1F024335282090A161718191A25262728292A3435363738393A434445464748494A535455565758595A636465666768696A737475767778797A838485868788898A92939495969798999AA2A3A4A5A6A7A8A9AAB2B3B4B5B6B7B8B9BAC2C3C4C5C6C7C8C9CAD2D3D4D5D6D7D8D9DAE1E2E3E4E5E6E7E8E9EAF1F2F3F4F5F6F7F8F9FAFFDA000C03010002110311003F00F9FE8A28A00FFFD9')
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
