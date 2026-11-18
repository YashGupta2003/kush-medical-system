"""Tests for Kush Pulse privacy-preserving regional heatmap."""
from datetime import date, timedelta

from app import models
from app.database import tenant_context
from app.services import heatmap_service


def _tenant(db, slug, region_code="MH-PUNE", opt_in=True):
    tenant = models.Tenant(
        slug=slug, shop_name=f"Shop {slug}", owner_name="Owner",
        email=f"{slug}@example.com", is_active=True,
        region_code=region_code, surveillance_opt_in=opt_in,
    )
    db.add(tenant)
    db.flush()
    return tenant


def _series(db, tenant, condition="Fever", spike_value=None, baseline=5, days=21):
    """Add `days` daily counts ending today, with an optional spike today."""
    end = date.today()
    for i in range(days):
        day = end - timedelta(days=days - 1 - i)
        value = spike_value if (spike_value is not None and i == days - 1) else baseline
        db.add(models.SurveillanceDailyCount(
            tenant_id=tenant.id, condition_name=condition,
            count_date=day, otc_units=value,
        ))
    db.flush()


def test_k_anonymity_suppresses_cells_with_fewer_than_three_tenants(db_session):
    first = _tenant(db_session, "heatmap-one")
    second = _tenant(db_session, "heatmap-two")
    _series(db_session, first, spike_value=200)
    _series(db_session, second, spike_value=200)
    db_session.commit()

    summary = heatmap_service.refresh_heatmap(db_session)
    result = heatmap_service.get_heatmap(db_session)

    assert summary["published_cells"] == 0
    assert summary["suppressed_cells"] == 1
    assert result["cells"] == []
    assert result["privacy"]["min_contributors"] == 3


def test_three_opted_in_tenants_publish_a_privacy_safe_cell(db_session):
    for i in range(3):
        tenant = _tenant(db_session, f"heatmap-ok-{i}")
        _series(db_session, tenant, spike_value=200)
    db_session.commit()

    summary = heatmap_service.refresh_heatmap(db_session)
    result = heatmap_service.get_heatmap(db_session)

    assert summary["published_cells"] == 1
    assert summary["suppressed_cells"] == 0
    assert len(result["cells"]) == 1
    cell = result["cells"][0]
    assert cell["contributor_count"] == 3
    assert cell["region_code"] == "MH-PUNE"
    assert cell["condition_name"] == "Fever"
    assert cell["signal_level"] in ("elevated", "critical")
    assert cell["trend"] == "up"
    assert cell["public_volume_band"] == "very high"
    assert cell["privacy_safe"] is True
    # Raw values and identifying fields must never appear in the public DTO.
    serialized = str(result)
    for forbidden in ("total_units", "otc_units", "tenant_id", "shop_name", "customer"):
        assert forbidden not in serialized


def test_opted_out_tenant_does_not_contribute(db_session):
    for i in range(3):
        _series(db_session, _tenant(db_session, f"heatmap-opt-{i}", opt_in=(i < 2)))
    db_session.commit()

    heatmap_service.refresh_heatmap(db_session)
    result = heatmap_service.get_heatmap(db_session)

    assert result["cells"] == []
    assert result["suppressed_cells"] == 1


def test_refresh_is_tenant_safe_from_a_scoped_request(db_session):
    tenants = [_tenant(db_session, f"heatmap-scoped-{i}") for i in range(3)]
    for tenant in tenants:
        _series(db_session, tenant, spike_value=180)
    db_session.commit()

    with tenant_context(db_session, tenants[0].id):
        summary = heatmap_service.refresh_heatmap(db_session)
        result = heatmap_service.get_heatmap(db_session)

    assert summary["published_cells"] == 1
    assert result["cells"][0]["contributor_count"] == 3


def test_refresh_is_idempotent(db_session):
    for i in range(3):
        _series(db_session, _tenant(db_session, f"heatmap-idem-{i}"))
    db_session.commit()

    heatmap_service.refresh_heatmap(db_session)
    heatmap_service.refresh_heatmap(db_session)

    assert db_session.query(models.RegionHeatmapRun).count() == 1
    assert db_session.query(models.RegionHeatmapSnapshot).count() == 1


def test_region_detail_returns_only_sanitized_cells(db_session):
    for i in range(3):
        _series(db_session, _tenant(db_session, f"heatmap-region-{i}"))
    db_session.commit()

    heatmap_service.refresh_heatmap(db_session)
    result = heatmap_service.get_region_heatmap(db_session, "mh-pune")

    assert result["region_code"] == "MH-PUNE"
    assert len(result["cells"]) == 1
    assert len(result["cells"][0]["trend_labels"]) == 7
    assert "total_units" not in result["cells"][0]
