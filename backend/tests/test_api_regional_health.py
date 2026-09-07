"""
API-level auth tests for Regional Health Sentinel endpoints.

Verifies the four mandatory auth behaviors:
  1. GET /regional-health/participation — any logged-in user (staff OK)
  2. PUT /regional-health/participation — owner only; staff gets 403
  3. GET /regional-health/alerts — any logged-in user (staff OK)
  4. POST /regional-health/scan-now — owner only; staff gets 403
  5. PATCH /regional-health/alerts/{id}/status — owner only; staff gets 403
"""
import pytest


def test_get_participation_as_staff(client, staff_headers, tenant):
    response = client.get("/v1/regional-health/participation", headers=staff_headers)
    assert response.status_code == 200
    data = response.json()
    assert "surveillance_opt_in" in data


def test_get_participation_as_owner(client, owner_headers, tenant):
    response = client.get("/v1/regional-health/participation", headers=owner_headers)
    assert response.status_code == 200


def test_update_participation_as_staff_is_forbidden(client, staff_headers, tenant):
    response = client.put(
        "/v1/regional-health/participation",
        headers=staff_headers,
        json={"region_code": "MUMBAI", "opt_in": True},
    )
    assert response.status_code == 403


def test_update_participation_as_owner(client, owner_headers, tenant):
    response = client.put(
        "/v1/regional-health/participation",
        headers=owner_headers,
        json={"region_code": "MUMBAI", "opt_in": True},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["region_code"] == "MUMBAI"
    assert data["surveillance_opt_in"] is True


def test_update_participation_requires_region_when_opting_in(client, owner_headers, tenant):
    response = client.put(
        "/v1/regional-health/participation",
        headers=owner_headers,
        json={"region_code": None, "opt_in": True},
    )
    assert response.status_code == 400


def test_get_alerts_as_staff(client, staff_headers, tenant):
    response = client.get("/v1/regional-health/alerts", headers=staff_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_alerts_returns_empty_when_not_opted_in(client, owner_headers, tenant):
    # Tenant defaults to surveillance_opt_in=False → should see empty list
    response = client.get("/v1/regional-health/alerts", headers=owner_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_trigger_scan_as_staff_is_forbidden(client, staff_headers):
    response = client.post("/v1/regional-health/scan-now", headers=staff_headers)
    assert response.status_code == 403


def test_trigger_scan_as_owner(client, owner_headers):
    response = client.post("/v1/regional-health/scan-now", headers=owner_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert "task_id" in response.json()


def test_update_alert_status_as_staff_is_forbidden(client, staff_headers):
    response = client.patch(
        "/v1/regional-health/alerts/999/status",
        headers=staff_headers,
        json={"status": "acknowledged"},
    )
    assert response.status_code == 403


def test_update_nonexistent_alert_as_owner_returns_404(client, owner_headers, tenant):
    # Need to opt in so the service runs; otherwise might 400 before 404
    client.put(
        "/v1/regional-health/participation",
        headers=owner_headers,
        json={"region_code": "TEST", "opt_in": True},
    )
    response = client.patch(
        "/v1/regional-health/alerts/99999/status",
        headers=owner_headers,
        json={"status": "acknowledged"},
    )
    assert response.status_code == 404
