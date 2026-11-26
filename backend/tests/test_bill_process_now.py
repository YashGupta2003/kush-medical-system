from io import BytesIO
from unittest.mock import patch

from PIL import Image

from app import models
from app.services.auth_service import create_access_token, hash_password


def _sample_png_bytes() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (200, 120), "white").save(buf, format="PNG")
    return buf.getvalue()


def test_process_bill_now_executes_queued_bill_and_enforces_tenant_isolation(
    client, db_session, owner_headers, tenant, tmp_path
):
    other_tenant = models.Tenant(
        slug="other-shop",
        shop_name="Other Pharmacy",
        owner_name="Other Owner",
        email="other@example.com",
    )
    db_session.add(other_tenant)
    db_session.commit()
    db_session.refresh(other_tenant)

    other_owner = models.User(
        username="other_owner",
        password_hash=hash_password("otherpass123"),
        full_name="Other Owner",
        role="owner",
        is_active=True,
        tenant_id=other_tenant.id,
    )
    db_session.add(other_owner)
    db_session.commit()
    db_session.refresh(other_owner)
    other_headers = {"Authorization": f"Bearer {create_access_token(other_owner)}"}

    img_path = tmp_path / "bill.png"
    img_path.write_bytes(_sample_png_bytes())

    bill = models.Bill(
        tenant_id=tenant.id,
        invoice_no="NOW-101",
        year=2026,
        month=11,
        image_path=str(img_path),
        status="queued",
    )
    db_session.add(bill)
    db_session.commit()
    db_session.refresh(bill)

    # Cross-tenant isolation check
    res_other = client.post(f"/v1/bills/{bill.id}/process-now", headers=other_headers)
    assert res_other.status_code == 404

    def fake_run(self):
        b = self.db.get(models.Bill, self.bill_id)
        b.status = "pending_review"
        b.ocr_confidence = 91.5
        self.db.commit()
        return {"status": "pending_review", "bill_id": self.bill_id}

    with patch("app.services.pipeline.BillProcessingPipeline.run", autospec=True, side_effect=fake_run):
        res = client.post(f"/v1/bills/{bill.id}/process-now", headers=owner_headers)

    assert res.status_code == 200
    data = res.json()
    assert data["id"] == bill.id
    assert data["status"] == "pending_review"
    assert data["ocr_confidence"] == 91.5
