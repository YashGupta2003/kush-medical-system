"""
Regional Health Sentinel — Cross-Tenant Disease Early-Warning Service.

PROBLEM THIS SOLVES:
  A single pharmacy's daily OTC sales are too noisy to reliably signal
  a real local health event (a viral outbreak, food-poisoning cluster,
  respiratory spike). But when MULTIPLE pharmacies in the same area ALL
  see a coordinated rise in the same condition on the same days, that is
  a statistically meaningful signal days before it would show up in hospital
  admission data. This service aggregates opted-in, privacy-safe daily
  counts across tenants to surface those regional signals.

PRIVACY-BY-AGGREGATION DESIGN:
  This service operates ONLY on SurveillanceDailyCount rows — the same
  privacy-safe (tenant_id, condition_name, count_date, otc_units) shape
  the existing single-tenant surveillance module already uses. It NEVER
  joins back to Sale, Customer, or Medicine tables. When a tenant views
  regional alerts, they see ONLY the combined regional total, a z-score,
  and a count of contributing pharmacies — never which specific other
  pharmacies contributed or their individual counts.

HONEST SCOPING NOTE — "region" as a string match:
  "Geographically near each other" in this feature means: tenants that
  have OPTED IN and share the same region_code string (e.g. a city
  name or postal-code prefix the Owner sets once in Settings). This is a
  deliberate, documented simplification — exactly the same pragmatic
  approach used in network_service.py (which documents simulated vs. real
  inter-pharmacy transport) and symptom_bot_service.py. Real geolocation/
  lat-long distance calculation would require a geocoding API, user
  location consent, and significant infrastructure for no meaningful
  improvement in this single-project context. Participation is OPT-IN per
  tenant (boolean flag defaulting to False) — a shop's daily counts are
  NEVER included in any regional aggregate unless its Owner has explicitly
  enabled this.
"""
import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.events.bus import event_bus
from app.events.events import RegionalHealthSpikeEvent
from app.services import anomaly_service
from app.services.audit_service import log_event


# ---------------------------------------------------------------------------
# Region string normalization
# Reuses the same uppercase-strip approach used by tenant_service._slugify
# for city names, and cross_tenant_integrity_service.normalize_batch for
# batch identifiers.
# ---------------------------------------------------------------------------

def _normalize_region_code(raw: str) -> str:
    """Strip surrounding whitespace, collapse internal runs, uppercase."""
    if not raw:
        return ""
    return " ".join(raw.strip().split()).upper()


# ---------------------------------------------------------------------------
# Part 1: Participation management
# ---------------------------------------------------------------------------

def get_or_create_region_participation(db: Session, tenant_id: int) -> dict:
    """Returns the current tenant's region_code and surveillance_opt_in values."""
    tenant = db.get(models.Tenant, tenant_id)
    if not tenant:
        return {"region_code": None, "surveillance_opt_in": False}
    return {
        "region_code": tenant.region_code,
        "surveillance_opt_in": bool(tenant.surveillance_opt_in),
    }


def update_region_participation(
    db: Session,
    tenant_id: int,
    region_code: Optional[str],
    opt_in: bool,
) -> dict:
    """
    Owner-only action (enforced at the router level) to set the tenant's
    region_code and opt-in flag. Validates and normalizes region_code.
    """
    tenant = db.get(models.Tenant, tenant_id)
    if not tenant:
        raise ValueError("Tenant not found")

    if opt_in:
        if not region_code or not region_code.strip():
            raise ValueError("A region_code is required when opting in to regional surveillance.")
        normalized = _normalize_region_code(region_code)
        if len(normalized) > 50:
            raise ValueError("region_code must be 50 characters or fewer.")
        tenant.region_code = normalized
    else:
        if region_code is not None and region_code.strip():
            tenant.region_code = _normalize_region_code(region_code)

    tenant.surveillance_opt_in = opt_in
    db.commit()
    db.refresh(tenant)

    return {
        "region_code": tenant.region_code,
        "surveillance_opt_in": bool(tenant.surveillance_opt_in),
    }


# ---------------------------------------------------------------------------
# Part 2: Regional spike scanning
# ---------------------------------------------------------------------------

def scan_regional_spikes(
    db: Session,
    days: int = 14,
    z_threshold: float = 2.0,
) -> dict:
    """
    Cross-tenant regional disease early-warning scan.

    Queries SurveillanceDailyCount JOINED to Tenant, filtered to opted-in
    tenants with a non-null region_code, grouped by (region_code,
    condition_name, count_date), summing otc_units and counting distinct
    contributing tenant_ids per group.

    Skips (region_code, condition_name) pairs with < 2 distinct opted-in
    contributors — this feature only adds value over the existing single-
    tenant detect_spikes() when there are 2+ contributors.

    Zero-fills daily series using the same pattern as
    surveillance_service.get_trend_data(), and runs
    anomaly_service._leave_one_out_zscores() on each series. Guards against
    zero-variance series using the same check as detect_spikes()
    (if max(counts) == min(counts): continue).

    For new spike alerts, publishes RegionalHealthSpikeEvent. On re-scan,
    updates stats without downgrading acknowledged/dismissed status to open.

    Privacy: NEVER joins to Sale, Customer, or Medicine tables.
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)

    # -----------------------------------------------------------------------
    # Step 1: Aggregate opted-in counts by (region_code, condition_name, count_date)
    # -----------------------------------------------------------------------
    rows = (
        db.query(
            models.Tenant.region_code,
            models.SurveillanceDailyCount.condition_name,
            models.SurveillanceDailyCount.count_date,
            func.sum(models.SurveillanceDailyCount.otc_units).label("total_units"),
            func.count(func.distinct(models.SurveillanceDailyCount.tenant_id)).label("tenant_count"),
        )
        .join(
            models.Tenant,
            models.SurveillanceDailyCount.tenant_id == models.Tenant.id,
        )
        .filter(
            models.Tenant.surveillance_opt_in.is_(True),
            models.Tenant.region_code.isnot(None),
            models.SurveillanceDailyCount.count_date >= start_date,
            models.SurveillanceDailyCount.count_date <= end_date,
        )
        .group_by(
            models.Tenant.region_code,
            models.SurveillanceDailyCount.condition_name,
            models.SurveillanceDailyCount.count_date,
        )
        .all()
    )

    # -----------------------------------------------------------------------
    # Step 2: Build in-memory structure
    # pair_data[(region_code, condition_name)][count_date] = (total_units, tenant_count)
    # -----------------------------------------------------------------------
    pair_data: Dict[tuple, Dict[date, tuple]] = defaultdict(dict)
    pair_max_tenants: Dict[tuple, int] = defaultdict(int)

    for row in rows:
        pair = (row.region_code, row.condition_name)
        pair_data[pair][row.count_date] = (int(row.total_units), int(row.tenant_count))
        if int(row.tenant_count) > pair_max_tenants[pair]:
            pair_max_tenants[pair] = int(row.tenant_count)

    new_alerts = 0
    updated_alerts = 0
    regions_seen: set = set()

    # -----------------------------------------------------------------------
    # Step 3: For each qualifying pair, run z-score analysis
    # -----------------------------------------------------------------------
    for (region_code, condition_name), day_map in pair_data.items():
        # Skip if fewer than 2 distinct tenants ever contributed
        if pair_max_tenants[(region_code, condition_name)] < 2:
            continue

        regions_seen.add(region_code)

        # Zero-fill daily series — same pattern as surveillance_service.get_trend_data()
        counts = []
        dates_in_order = []
        for i in range(days):
            d = start_date + timedelta(days=i)
            dates_in_order.append(d)
            entry = day_map.get(d)
            counts.append(entry[0] if entry else 0)

        if sum(counts) == 0 or len(counts) < 3:
            continue

        # Guard against zero-variance series — same check as detect_spikes()
        if max(counts) == min(counts):
            continue

        z_scores = anomaly_service._leave_one_out_zscores(counts)

        for i, z in z_scores.items():
            if not (math.isfinite(z) and z >= z_threshold and counts[i] > 0):
                continue

            alert_date = dates_in_order[i]
            total_units = counts[i]
            day_entry = day_map.get(alert_date)
            day_tenant_count = day_entry[1] if day_entry else pair_max_tenants[(region_code, condition_name)]

            # Regional average = mean of all OTHER days (leave-one-out)
            other_counts = [counts[j] for j in range(len(counts)) if j != i]
            regional_avg = sum(other_counts) / max(1, len(other_counts))

            # Severity classification
            if z >= 3.0:
                severity = "critical"
            elif z >= 2.5:
                severity = "elevated"
            else:
                severity = "watch"

            # Upsert logic
            existing = (
                db.query(models.RegionalHealthAlert)
                .filter_by(
                    region_code=region_code,
                    condition_name=condition_name,
                    alert_date=alert_date,
                )
                .first()
            )

            if existing:
                # Update aggregate stats
                existing.contributing_tenant_count = day_tenant_count
                existing.total_regional_units = total_units
                existing.regional_avg_units = Decimal(str(round(regional_avg, 2)))
                existing.z_score = Decimal(str(round(z, 3)))
                # Never downgrade acknowledged/dismissed back to open
                if existing.status == "open":
                    existing.severity = severity
                existing.updated_at = datetime.now(timezone.utc)
                updated_alerts += 1
            else:
                new_alert = models.RegionalHealthAlert(
                    region_code=region_code,
                    condition_name=condition_name,
                    alert_date=alert_date,
                    contributing_tenant_count=day_tenant_count,
                    total_regional_units=total_units,
                    regional_avg_units=Decimal(str(round(regional_avg, 2))),
                    z_score=Decimal(str(round(z, 3))),
                    severity=severity,
                    status="open",
                )
                db.add(new_alert)
                db.flush()

                event_bus.publish(RegionalHealthSpikeEvent(
                    alert_id=new_alert.id,
                    region_code=region_code,
                    condition_name=condition_name,
                    contributing_tenant_count=day_tenant_count,
                    z_score=float(z),
                    db=db,
                ))
                new_alerts += 1

    db.commit()

    return {
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "regions_scanned": len(regions_seen),
        "new_alerts": new_alerts,
        "updated_alerts": updated_alerts,
    }


# ---------------------------------------------------------------------------
# Part 3: Alert retrieval
# ---------------------------------------------------------------------------

def get_alerts_for_tenant(
    db: Session,
    tenant_id: int,
    status: str = "open",
) -> List[Dict[str, Any]]:
    """
    Returns regional health alerts visible to this tenant.

    Returns empty list immediately if the tenant is not opted in or has no
    region_code — they should see nothing if not participating.

    Privacy: returned dicts NEVER include region_code, tenant_ids, shop
    names, or any other-tenant-identifying field. Only combined aggregate
    stats are exposed.
    """
    tenant = db.get(models.Tenant, tenant_id)
    if not tenant or not tenant.region_code or not tenant.surveillance_opt_in:
        return []

    alerts = (
        db.query(models.RegionalHealthAlert)
        .filter_by(region_code=tenant.region_code, status=status)
        .order_by(models.RegionalHealthAlert.alert_date.desc())
        .all()
    )

    return [
        {
            "id": a.id,
            "condition_name": a.condition_name,
            "alert_date": a.alert_date.isoformat() if a.alert_date else None,
            "contributing_tenant_count": a.contributing_tenant_count,
            "total_regional_units": a.total_regional_units,
            "regional_avg_units": float(a.regional_avg_units),
            "z_score": float(a.z_score),
            "severity": a.severity,
            "status": a.status,
        }
        for a in alerts
    ]


# ---------------------------------------------------------------------------
# Part 4: Alert status management
# ---------------------------------------------------------------------------

def update_alert_status(
    db: Session,
    alert_id: int,
    tenant_id: int,
    new_status: str,
) -> dict:
    """
    Allows a tenant in the same region to acknowledge or dismiss an alert.

    Raises ValueError if the calling tenant's region_code does not match
    the alert's region_code, or if the alert is not found.
    """
    if new_status not in ("acknowledged", "dismissed"):
        raise ValueError("Invalid status — must be 'acknowledged' or 'dismissed'.")

    alert = db.get(models.RegionalHealthAlert, alert_id)
    if not alert:
        raise ValueError("Alert not found")

    tenant = db.get(models.Tenant, tenant_id)
    if not tenant or tenant.region_code != alert.region_code:
        raise ValueError("Not authorized for this region")

    alert.status = new_status
    alert.updated_at = datetime.now(timezone.utc)

    log_event(db, "regional_alert_status_changed", alert.id, {
        "alert_id": alert_id,
        "tenant_id": tenant_id,
        "condition_name": alert.condition_name,
        "alert_date": str(alert.alert_date),
        "new_status": new_status,
    })

    db.commit()
    return {
        "id": alert.id,
        "status": alert.status,
        "condition_name": alert.condition_name,
        "alert_date": alert.alert_date.isoformat() if alert.alert_date else None,
    }
