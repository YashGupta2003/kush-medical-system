import pytest

def test_get_alerts_as_staff(client, staff_headers, db_session, tenant, sample_medicine):
    response = client.get("/v1/network-integrity/alerts", headers=staff_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_update_alert_as_staff_is_forbidden(client, staff_headers, db_session, tenant, sample_medicine):
    response = client.patch(
        "/v1/network-integrity/alerts/1/status",
        headers=staff_headers,
        json={"status": "reviewed"}
    )
    assert response.status_code == 403

def test_trigger_scan_as_staff_is_forbidden(client, staff_headers):
    response = client.post("/v1/network-integrity/scan-now", headers=staff_headers)
    assert response.status_code == 403

def test_trigger_scan_as_owner(client, owner_headers):
    response = client.post("/v1/network-integrity/scan-now", headers=owner_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert "task_id" in response.json()
