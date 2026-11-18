"""API-level tests for Kush Pulse privacy guarantees."""
from datetime import date, timedelta

from app import models
from app.services import heatmap_service


def _seed_optional_heatmap(db):
    tenants = []
    for index in range(3):
        tenant = models.Tenant(
            slug=f"api-heatmap-{index}",
            shop_name=f"Shop {index}",
            owner_name="Owner",
            email=f"api-heatmap-{index}@example.com",
            is_active=True,
            region_code="MH-PUNE",
            surveillance_opt_in=True,
        )
        db.add(tenant)
        db.flush()
        tenants.append(tenant)

    end = date.today()
    for tenant in tenants:
        for i in range(21):
            day = end - timedelta(days=20 - i)
            db.add(models.SurveillanceDailyCount(
                tenant_id=tenant.id,
                condition_name="Fever",
                count_date=day,
                otc_units=200 if i == 20 else 5,
            ))
    db.commit()


def test_public_heatmap_exposes_only_sanitized_fields(client, db_session, owner_headers):
    _seed_optional_heatmap(db_session)

    refresh = client.post("/v1/heatmap/refresh", headers=owner_headers)
    assert refresh.status_code == 200, refresh.text

    response = client.get("/v1/heatmap/regional")

    assert response.status_code == 200
    body = response.json()
    assert body["privacy"]["min_contributors"] == 3
    assert body["privacy"]["individual_data_included"] is False
    assert len(body["cells"]) == 1
    cell = body["cells"][0]
    assert set(cell) == {
        "region_code", "condition_name", "signal_level", "trend", "trend_labels",
        "contributor_count", "public_volume_band", "confidence", "privacy_safe",
    }


def test_region_detail_endpoint_returns_sanitized_cells(client, db_session, owner_headers):
    _seed_optional_heatmap(db_session)
    assert client.post("/v1/heatmap/refresh", headers=owner_headers).status_code == 200

    response = client.get("/v1/heatmap/regions/mh-pune")

    assert response.status_code == 200
    body = response.json()
    assert body["region_code"] == "MH-PUNE"
    assert body["cells"][0]["contributor_count"] == 3


def test_heatmap_refresh_requires_owner(client, staff_headers):
    response = client.post("/v1/heatmap/refresh", headers=staff_headers)
    assert response.status_code == 403


def test_heatmap_helpers_are_public_safe_without_a_snapshot(client):
    response = client.get("/v1/heatmap/regional")
    assert response.status_code == 200
    assert response.json()["cells"] == []
