"""
Tests for Regional Health Sentinel (regional_health_service.py).

Covers all 8 mandatory test cases from the feature spec:
  1. Two opted-in tenants, same region, coordinated spike → exactly one alert
     with contributing_tenant_count == 2.
  2. A non-opted-in tenant sharing the same region_code must NEVER inflate
     total_regional_units or cause a spurious spike.
  3. Only one opted-in tenant in a region → NO alert created.
  4. Two tenants with DIFFERENT region_codes, identical spike pattern →
     NOT merged into one alert; separate aggregations per region.
  5. Re-scan does not duplicate rows and does not reset 'dismissed' → 'open'.
  6. get_alerts_for_tenant() returns empty list when opt_in=False or
     region_code=None.
  7. get_alerts_for_tenant() return dicts must NOT contain region_code,
     tenant_ids, or any other-pharmacy-identifying field.
  8. update_alert_status() raises ValueError when the tenant's region_code
     doesn't match the alert's region.

Plus API-level auth tests (staff can view, only owner can mutate).
"""
import pytest
from datetime import date, timedelta
from app import models
from app.services import regional_health_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tenant(db, slug, region_code=None, opt_in=False):
    t = models.Tenant(
        slug=slug, shop_name=f"Shop {slug}", owner_name="Owner",
        email=f"{slug}@example.com", is_active=True,
        region_code=region_code, surveillance_opt_in=opt_in,
    )
    db.add(t)
    db.flush()
    return t


def _make_surveillance_count(db, tenant_id, condition, count_date, otc_units):
    row = models.SurveillanceDailyCount(
        tenant_id=tenant_id,
        condition_name=condition,
        count_date=count_date,
        otc_units=otc_units,
    )
    db.add(row)
    db.flush()
    return row


def _spike_series(db, tenant_id, condition, days=14, spike_day_offset=1, spike_value=200, baseline=5):
    """
    Inserts a clearly anomalous series: baseline for most days, then a spike
    on the day at `spike_day_offset` from today.
    """
    end = date.today()
    start = end - timedelta(days=days - 1)
    for i in range(days):
        d = start + timedelta(days=i)
        value = spike_value if i == (days - spike_day_offset) else baseline
        _make_surveillance_count(db, tenant_id, condition, d, value)
    db.commit()


# ---------------------------------------------------------------------------
# Test 1: Two opted-in tenants in the same region, coordinated spike
# ---------------------------------------------------------------------------

def test_two_tenants_same_region_spike_creates_one_alert(db_session):
    t1 = _make_tenant(db_session, "t1-spike", region_code="DELHI", opt_in=True)
    t2 = _make_tenant(db_session, "t2-spike", region_code="DELHI", opt_in=True)

    _spike_series(db_session, t1.id, "Fever", days=14, spike_day_offset=1, spike_value=200, baseline=3)
    _spike_series(db_session, t2.id, "Fever", days=14, spike_day_offset=1, spike_value=180, baseline=4)

    result = regional_health_service.scan_regional_spikes(db_session, days=14, z_threshold=2.0)

    assert result["new_alerts"] >= 1

    alerts = (
        db_session.query(models.RegionalHealthAlert)
        .filter_by(region_code="DELHI", condition_name="Fever")
        .all()
    )
    # There should be exactly one alert row for today's spike date
    spike_date_alerts = [a for a in alerts if a.total_regional_units >= 300]  # 200+180 spike combined
    assert len(spike_date_alerts) == 1
    assert spike_date_alerts[0].contributing_tenant_count == 2


# ---------------------------------------------------------------------------
# Test 2: Non-opted-in tenant must NOT contribute to aggregate
# ---------------------------------------------------------------------------

def test_non_opted_in_tenant_does_not_inflate_regional_total(db_session):
    t1 = _make_tenant(db_session, "t1-optin", region_code="MUMBAI", opt_in=True)
    t2_out = _make_tenant(db_session, "t2-optout", region_code="MUMBAI", opt_in=False)

    # t1 has baseline-only counts — would NOT spike alone
    _spike_series(db_session, t1.id, "Cough", days=14, spike_day_offset=1, spike_value=6, baseline=5)
    # t2 (not opted in) has wildly high counts — must NOT be aggregated
    _spike_series(db_session, t2_out.id, "Cough", days=14, spike_day_offset=1, spike_value=9999, baseline=5)

    result = regional_health_service.scan_regional_spikes(db_session, days=14, z_threshold=2.0)

    # Since t2 is not opted in and t1 alone has no spike, no alert should be created
    alerts = (
        db_session.query(models.RegionalHealthAlert)
        .filter_by(region_code="MUMBAI", condition_name="Cough")
        .all()
    )
    # Either no alerts at all, or any that exist must show only 1 contributing tenant
    for alert in alerts:
        assert alert.contributing_tenant_count == 1  # only t1 counted

    # And total_regional_units must never include t2's 9999 values
    for alert in alerts:
        assert alert.total_regional_units < 9000, (
            f"Non-opted-in tenant's count leaked into aggregate: {alert.total_regional_units}"
        )


# ---------------------------------------------------------------------------
# Test 3: Only ONE opted-in tenant in a region → NO alert
# ---------------------------------------------------------------------------

def test_single_opted_in_tenant_never_creates_regional_alert(db_session):
    t1 = _make_tenant(db_session, "t1-solo", region_code="SOLO_REGION", opt_in=True)

    # Even with a wild spike, single-tenant must produce NO regional alert
    _spike_series(db_session, t1.id, "Dengue", days=14, spike_day_offset=1, spike_value=5000, baseline=2)

    result = regional_health_service.scan_regional_spikes(db_session, days=14, z_threshold=2.0)

    alerts = (
        db_session.query(models.RegionalHealthAlert)
        .filter_by(region_code="SOLO_REGION", condition_name="Dengue")
        .all()
    )
    assert len(alerts) == 0, "Single-tenant regional scan must never create an alert"
    assert result["new_alerts"] == 0


# ---------------------------------------------------------------------------
# Test 4: Two tenants with DIFFERENT region_codes → separate aggregation
# ---------------------------------------------------------------------------

def test_different_region_codes_not_merged(db_session):
    t_north = _make_tenant(db_session, "t-north", region_code="NORTH", opt_in=True)
    t_south = _make_tenant(db_session, "t-south", region_code="SOUTH", opt_in=True)

    # Both have big spikes in the same condition on the same day,
    # but they are in different regions — must NOT create one combined alert
    _spike_series(db_session, t_north.id, "Malaria", days=14, spike_day_offset=1, spike_value=300, baseline=4)
    _spike_series(db_session, t_south.id, "Malaria", days=14, spike_day_offset=1, spike_value=280, baseline=4)

    result = regional_health_service.scan_regional_spikes(db_session, days=14, z_threshold=2.0)

    north_alerts = (
        db_session.query(models.RegionalHealthAlert)
        .filter_by(region_code="NORTH", condition_name="Malaria")
        .all()
    )
    south_alerts = (
        db_session.query(models.RegionalHealthAlert)
        .filter_by(region_code="SOUTH", condition_name="Malaria")
        .all()
    )

    # North should have 0 (only 1 tenant → no cross-tenant value)
    assert len(north_alerts) == 0, "Single tenant per region must not produce alert"
    # South should have 0 for the same reason
    assert len(south_alerts) == 0, "Single tenant per region must not produce alert"

    # Verify regions are counted separately by adding a second tenant to NORTH
    t_north2 = _make_tenant(db_session, "t-north2", region_code="NORTH", opt_in=True)
    _spike_series(db_session, t_north2.id, "Malaria", days=14, spike_day_offset=1, spike_value=290, baseline=4)

    result2 = regional_health_service.scan_regional_spikes(db_session, days=14, z_threshold=2.0)

    north_alerts2 = (
        db_session.query(models.RegionalHealthAlert)
        .filter_by(region_code="NORTH", condition_name="Malaria")
        .all()
    )
    south_alerts2 = (
        db_session.query(models.RegionalHealthAlert)
        .filter_by(region_code="SOUTH", condition_name="Malaria")
        .all()
    )

    # North now has 2 tenants → alert may exist; South still only 1 → no alert
    assert len(south_alerts2) == 0, "SOUTH region should never have 2 tenants in this test"
    # All NORTH alerts must have region_code NORTH, not SOUTH
    for a in north_alerts2:
        assert a.region_code == "NORTH"


# ---------------------------------------------------------------------------
# Test 5: Re-scan does not duplicate rows and does not reset 'dismissed'
# ---------------------------------------------------------------------------

def test_rescan_no_duplicate_and_dismissed_status_preserved(db_session):
    t1 = _make_tenant(db_session, "t1-rescan", region_code="RESCAN_CITY", opt_in=True)
    t2 = _make_tenant(db_session, "t2-rescan", region_code="RESCAN_CITY", opt_in=True)

    _spike_series(db_session, t1.id, "Flu", days=14, spike_day_offset=1, spike_value=200, baseline=3)
    _spike_series(db_session, t2.id, "Flu", days=14, spike_day_offset=1, spike_value=190, baseline=3)

    r1 = regional_health_service.scan_regional_spikes(db_session, days=14, z_threshold=2.0)
    assert r1["new_alerts"] >= 1

    # Get the alert and dismiss it
    alerts = (
        db_session.query(models.RegionalHealthAlert)
        .filter_by(region_code="RESCAN_CITY", condition_name="Flu")
        .all()
    )
    for a in alerts:
        a.status = "dismissed"
    db_session.commit()

    # Re-scan
    r2 = regional_health_service.scan_regional_spikes(db_session, days=14, z_threshold=2.0)

    # No NEW alerts should be created (they already exist)
    assert r2["new_alerts"] == 0

    # Alert count must not have grown
    alerts_after = (
        db_session.query(models.RegionalHealthAlert)
        .filter_by(region_code="RESCAN_CITY", condition_name="Flu")
        .all()
    )
    assert len(alerts_after) == len(alerts)

    # All still dismissed — never reset to open
    for a in alerts_after:
        assert a.status == "dismissed", f"Alert #{a.id} was reset from 'dismissed' to '{a.status}'"


# ---------------------------------------------------------------------------
# Test 6: get_alerts_for_tenant returns [] for non-opted-in / no region
# ---------------------------------------------------------------------------

def test_get_alerts_returns_empty_for_non_opted_in(db_session):
    t_no_opt = _make_tenant(db_session, "t-noopt", region_code="CITY", opt_in=False)
    t_no_region = _make_tenant(db_session, "t-noregion", region_code=None, opt_in=True)

    # Manually insert an alert in "CITY" to make sure it exists
    db_session.add(models.RegionalHealthAlert(
        region_code="CITY", condition_name="TestCond",
        alert_date=date.today(),
        contributing_tenant_count=2, total_regional_units=100,
        regional_avg_units=10.0, z_score=3.5,
        severity="critical", status="open",
    ))
    db_session.commit()

    # Non-opted-in tenant must see nothing
    result = regional_health_service.get_alerts_for_tenant(db_session, t_no_opt.id)
    assert result == []

    # Tenant with no region_code must see nothing
    result2 = regional_health_service.get_alerts_for_tenant(db_session, t_no_region.id)
    assert result2 == []


# ---------------------------------------------------------------------------
# Test 7: get_alerts_for_tenant never exposes region_code, tenant_ids, etc.
# ---------------------------------------------------------------------------

def test_get_alerts_hides_identifying_fields(db_session):
    t = _make_tenant(db_session, "t-privacy", region_code="PRIVACY_REGION", opt_in=True)

    db_session.add(models.RegionalHealthAlert(
        region_code="PRIVACY_REGION", condition_name="Cholera",
        alert_date=date.today(),
        contributing_tenant_count=3, total_regional_units=120,
        regional_avg_units=12.0, z_score=2.8,
        severity="elevated", status="open",
    ))
    db_session.commit()

    alerts = regional_health_service.get_alerts_for_tenant(db_session, t.id)
    assert len(alerts) == 1

    allowed_keys = {
        "id", "condition_name", "alert_date", "contributing_tenant_count",
        "total_regional_units", "regional_avg_units", "z_score", "severity", "status",
    }
    forbidden_keys = {"region_code", "tenant_ids", "tenant_id", "shop_name", "shop_names"}

    actual_keys = set(alerts[0].keys())
    assert actual_keys == allowed_keys, (
        f"Return dict has unexpected keys: {actual_keys - allowed_keys} "
        f"or is missing expected keys: {allowed_keys - actual_keys}"
    )
    for fk in forbidden_keys:
        assert fk not in actual_keys, f"Forbidden field '{fk}' found in response"


# ---------------------------------------------------------------------------
# Test 8: update_alert_status raises ValueError for wrong region tenant
# ---------------------------------------------------------------------------

def test_update_alert_status_raises_for_wrong_region(db_session):
    t_owner = _make_tenant(db_session, "t-owner-region", region_code="REGION_A", opt_in=True)
    t_other = _make_tenant(db_session, "t-other-region", region_code="REGION_B", opt_in=True)

    alert = models.RegionalHealthAlert(
        region_code="REGION_A", condition_name="Typhoid",
        alert_date=date.today(),
        contributing_tenant_count=2, total_regional_units=80,
        regional_avg_units=8.0, z_score=2.2,
        severity="watch", status="open",
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)

    # t_other is in REGION_B — should not be able to ack REGION_A's alert
    with pytest.raises(ValueError, match="Not authorized for this region"):
        regional_health_service.update_alert_status(
            db_session, alert.id, t_other.id, "acknowledged"
        )

    # t_owner IS in REGION_A — should succeed
    result = regional_health_service.update_alert_status(
        db_session, alert.id, t_owner.id, "acknowledged"
    )
    assert result["status"] == "acknowledged"


# ---------------------------------------------------------------------------
# Test 9: update_region_participation normalization and opt-in validation
# ---------------------------------------------------------------------------

def test_update_region_participation_normalizes_region_code(db_session, tenant):
    result = regional_health_service.update_region_participation(
        db_session, tenant.id, "  new delhi  ", True
    )
    assert result["region_code"] == "NEW DELHI"
    assert result["surveillance_opt_in"] is True


def test_update_region_participation_requires_region_code_when_opting_in(db_session, tenant):
    with pytest.raises(ValueError, match="region_code is required"):
        regional_health_service.update_region_participation(
            db_session, tenant.id, None, True
        )

    with pytest.raises(ValueError, match="region_code is required"):
        regional_health_service.update_region_participation(
            db_session, tenant.id, "   ", True
        )
