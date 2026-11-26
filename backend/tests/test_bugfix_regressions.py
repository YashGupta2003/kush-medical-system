"""Regression tests covering critical runtime, DB, API contract, and security fixes."""
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from app import models
from app.services.auth_service import create_access_token, hash_password


def test_analytics_inventory_valuation_and_dead_stock(client, db_session, tenant, owner_headers, staff_headers, sample_medicine):
    # Create a second medicine with stock and one recent sale on sample_medicine
    slow_med = models.Medicine(
        particulars="SLOW MOVING SYRUP",
        normalized_name="SLOWMOVINGSYRUP",
        unit="100ML",
        mrp=200.0,
        net_rate=120.0,
        current_stock=5,
        tenant_id=tenant.id,
    )
    db_session.add(slow_med)
    db_session.flush()

    sale = models.Sale(
        tenant_id=tenant.id,
        medicine_id=sample_medicine.id,
        qty_sold=2,
        sold_at=datetime.now(timezone.utc),
    )
    db_session.add(sale)
    db_session.commit()

    val_res = client.get("/v1/analytics/inventory-valuation", headers=owner_headers)
    assert val_res.status_code == 200
    val = val_res.json()
    # sample_medicine: 20 * 61.18 = 1223.60, slow_med: 5 * 120.0 = 600.0 -> 1823.60
    assert val["total_cost_value"] == 1823.6
    # sample_medicine: 20 * 118.53 = 2370.60, slow_med: 5 * 200.0 = 1000.0 -> 3370.60
    assert val["total_retail_value"] == 3370.6
    assert val["in_stock_sku_count"] == 2
    assert len(val["top_valued_items"]) == 2

    dead_res = client.get("/v1/analytics/dead-stock?days=90", headers=owner_headers)
    assert dead_res.status_code == 200
    dead = dead_res.json()
    assert dead["dead_stock_count"] == 1
    assert dead["items"][0]["medicine_id"] == slow_med.id
    assert dead["total_tied_up_value"] == 600.0

    # Owner-only enforcement
    assert client.get("/v1/analytics/inventory-valuation", headers=staff_headers).status_code == 403
    assert client.get("/v1/analytics/dead-stock", headers=staff_headers).status_code == 403


def test_smart_purchase_whatsapp_reports_honest_delivery_status(client, owner_headers):
    payload = {
        "distributor_name": "HARI KRISHNA",
        "phone": "+919876543210",
        "items": [{"medicine_name": "DOLO 650", "order_qty": 10, "unit": "strip"}],
    }

    with patch("app.services.whatsapp_service.send_message", return_value=False):
        res = client.post("/v1/smart-purchase/send-whatsapp", json=payload, headers=owner_headers)
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "failed"
        assert "not configured" in body["error"].lower()

    with patch("app.services.whatsapp_service.send_message", return_value=True):
        res = client.post("/v1/smart-purchase/send-whatsapp", json=payload, headers=owner_headers)
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "success"


def test_profit_substitutes_handles_missing_medicine_and_empty_graph(client, owner_headers, sample_medicine):
    # Non-existent medicine should return 404 instead of 500 ResponseValidationError
    missing_res = client.get("/v1/profit/substitutes/999999", headers=owner_headers)
    assert missing_res.status_code == 404

    # Existing medicine without graph edges still returns valid empty schema
    empty_res = client.get(f"/v1/profit/substitutes/{sample_medicine.id}", headers=owner_headers)
    assert empty_res.status_code == 200
    body = empty_res.json()
    assert body["medicine_id"] == sample_medicine.id
    assert body["name"] == sample_medicine.particulars
    assert body["substitutes"] == []


def test_staff_can_access_distributor_confidence_only(client, sample_distributor, staff_headers):
    conf_res = client.get(
        f"/v1/trust-score/distributors/{sample_distributor.id}/confidence",
        headers=staff_headers,
    )
    assert conf_res.status_code == 200

    # Other trust-score endpoints remain owner-only
    assert client.get("/v1/trust-score/distributors", headers=staff_headers).status_code == 403
    assert client.get("/v1/trust-score/batch-collisions", headers=staff_headers).status_code == 403


def test_staff_net_rate_masked_on_single_medicine_endpoints(client, db_session, sample_medicine, owner_headers, staff_headers):
    # Assign barcode as owner
    patch_bc = client.patch(
        f"/v1/medicines/{sample_medicine.id}/barcode",
        json={"barcode": "8901234567890"},
        headers=owner_headers,
    )
    assert patch_bc.status_code == 200
    assert patch_bc.json()["net_rate"] == 61.18

    # Staff queries must mask net_rate across all single-item routes
    get_res = client.get(f"/v1/medicines/{sample_medicine.id}", headers=staff_headers)
    assert get_res.status_code == 200
    assert get_res.json()["net_rate"] is None

    bc_res = client.get("/v1/medicines/barcode/8901234567890", headers=staff_headers)
    assert bc_res.status_code == 200
    assert bc_res.json()["found"] is True
    assert bc_res.json()["medicine"]["net_rate"] is None

    comp_res = client.patch(
        f"/v1/medicines/{sample_medicine.id}/composition",
        json={"composition": "Amlodipine 5mg + Atenolol 50mg"},
        headers=staff_headers,
    )
    assert comp_res.status_code == 200
    assert comp_res.json()["net_rate"] is None


def test_cold_chain_excursion_commits_audit_and_notification(client, db_session, owner_headers):
    unit_res = client.post(
        "/v1/cold-chain/units",
        json={"unit_label": "Vaccine Fridge A", "min_temp_c": 2.0, "max_temp_c": 8.0},
        headers=owner_headers,
    )
    assert unit_res.status_code == 200
    unit_id = unit_res.json()["id"]

    reading_res = client.post(
        "/v1/cold-chain/readings",
        json={"unit_id": unit_id, "recorded_temp_c": 14.5, "note": "Door left open"},
        headers=owner_headers,
    )
    assert reading_res.status_code == 200
    reading_id = reading_res.json()["id"]

    audit_entries = (
        db_session.query(models.AuditLedgerEntry)
        .filter(
            models.AuditLedgerEntry.event_type == "cold_chain_reading",
            models.AuditLedgerEntry.reference_id == reading_id,
        )
        .all()
    )
    assert len(audit_entries) == 1

    notif_res = client.get("/v1/notifications?unread_only=true&page=1&page_size=20", headers=owner_headers)
    assert notif_res.status_code == 200
    items = notif_res.json()["items"]
    assert any(
        n["related_entity_type"] == "cold_chain_unit" and n["severity"] == "critical"
        for n in items
    )


def test_auth_cookie_secure_flag_matches_transport_scheme(client, owner_user):
    res_http = client.post(
        "/v1/auth/login",
        json={"username": owner_user.username, "password": "ownerpass123", "tenant_id": owner_user.tenant_id},
    )
    assert res_http.status_code == 200
    cookie_header_http = res_http.headers.get("set-cookie", "")
    assert "refresh_token=" in cookie_header_http
    assert "; Secure" not in cookie_header_http

    res_https = client.post(
        "/v1/auth/login",
        json={"username": owner_user.username, "password": "ownerpass123", "tenant_id": owner_user.tenant_id},
        headers={"X-Forwarded-Proto": "https"},
    )
    assert res_https.status_code == 200
    cookie_header_https = res_https.headers.get("set-cookie", "")
    assert "; Secure" in cookie_header_https


def test_pipeline_runs_with_distributor_template_lookup(db_session, tenant, sample_distributor):
    from app.services.pipeline import BillProcessingPipeline
    from app.services.ocr_service import OcrResult

    # Minimal 1x1 PNG upload bytes on disk via temp file cleanup
    tmp_path = "/tmp/pharmos_test_bill.png"
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xff\xff"
        b"?\x00\x05\xfe\x02\xfeA\x89\x9c\xb5\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    with open(tmp_path, "wb") as f:
        f.write(png_bytes)

    bill = models.Bill(
        tenant_id=tenant.id,
        distributor_id=sample_distributor.id,
        year=2026,
        month=3,
        image_path=tmp_path,
        status="queued",
    )
    db_session.add(bill)
    db_session.commit()
    db_session.refresh(bill)

    try:
        fake_ocr = OcrResult(
            full_text="PARACETAMOL 500 10 25.00 18.00",
            words=[],
            avg_confidence=95.0,
            engine_used="mock",
        )
        with patch("app.services.pipeline.image_preprocessing.preprocess_bill_image", side_effect=RuntimeError("skip")), \
             patch("app.services.pipeline.run_ocr", return_value=fake_ocr):
            BillProcessingPipeline(bill.id, db_session).run()
        db_session.refresh(bill)
        assert bill.status in ("pending_review", "needs_attention")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_voice_confirm_rejects_non_positive_quantity(client, owner_headers, sample_medicine):
    res = client.post(
        "/v1/voice/confirm",
        json={"intent": "sell", "medicine_id": sample_medicine.id, "quantity": 0},
        headers=owner_headers,
    )
    assert res.status_code == 422


def test_deactivate_user_is_tenant_isolated(client, db_session, owner_headers):
    other_tenant = models.Tenant(
        slug="other-shop", shop_name="Other Shop", owner_name="Other Owner", email="other@example.com"
    )
    db_session.add(other_tenant)
    db_session.flush()
    other_user = models.User(
        username="other_staff",
        password_hash=hash_password("pass123456"),
        role="staff",
        is_active=True,
        tenant_id=other_tenant.id,
    )
    db_session.add(other_user)
    db_session.commit()

    res = client.patch(f"/v1/auth/users/{other_user.id}/deactivate", headers=owner_headers)
    assert res.status_code == 404


def test_register_lookup_and_login_are_case_insensitive_for_usernames(client, db_session, tenant, staff_user):
    # Staff login via mixed-case username lookup + login should succeed cleanly
    lookup_res = client.post("/v1/register/lookup", json={"email": f"  {staff_user.username.upper()}  "})
    assert lookup_res.status_code == 200
    assert lookup_res.json()["tenant_id"] == tenant.id

    login_res = client.post(
        "/v1/auth/login",
        json={"username": f"  {staff_user.username.upper()} ", "password": "staffpass123", "tenant_id": tenant.id},
    )
    assert login_res.status_code == 200
    assert login_res.json()["username"] == staff_user.username

