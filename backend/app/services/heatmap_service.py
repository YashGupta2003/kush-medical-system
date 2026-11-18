"""
Kush Pulse — Privacy-Preserving Regional Health Heatmap.

This module converts opted-in, privacy-safe OTC counts into a regional
signal map that reveals a trend without revealing a shop, customer, bill,
medicine or distributor.

Privacy contract
----------------
1. Only ``SurveillanceDailyCount`` rows are read. This module NEVER joins to
   Sale, Customer, Bill, Medicine or Distributor.
2. A (region, condition) cell is published only when at least
   ``HEATMAP_MIN_CONTRIBUTORS`` distinct opted-in tenants contributed during
   the window. Below that threshold the cell is suppressed entirely.
3. A 7-day window plus a 14-day baseline is used instead of a single day, so
   one unusual day at one shop cannot identify that shop.
4. Only signal labels and contributor counts are exposed publicly. Raw unit
   totals are bucketed into bands before serialization.
5. Snapshot tables are intentionally global (no ``tenant_id``) because they
   are cross-shop aggregates. Privacy comes from the k-anonymity rule above,
   not from tenant scoping the aggregate table.

The existing Regional Health Sentinel alert threshold is deliberately kept at
2 contributors. Alerts go to authorized shop owners; this heatmap is a
publishable view and therefore uses the stricter threshold of 3.
"""
import hashlib
import json
import math
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.database import bypass_tenant_filter
from app.services import anomaly_service

HEATMAP_MIN_CONTRIBUTORS = 3
DEFAULT_WINDOW_DAYS = 7
DEFAULT_BASELINE_DAYS = 14

_SIGNAL_ORDER = {"stable": 0, "watch": 1, "elevated": 2, "critical": 3}
_VOLUME_ORDER = {"low": 0, "moderate": 1, "high": 2, "very high": 3}


def _canonical(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _classify_signal(z_score: float) -> str:
    if not math.isfinite(z_score):
        return "stable"
    if z_score >= 3.5:
        return "critical"
    if z_score >= 2.5:
        return "elevated"
    if z_score >= 1.5:
        return "watch"
    return "stable"


def _classify_volume(total_units: int) -> str:
    if total_units <= 50:
        return "low"
    if total_units <= 200:
        return "moderate"
    if total_units <= 500:
        return "high"
    return "very high"


def _classify_trend(window_counts: List[int]) -> str:
    """Compare the last 3 days with the preceding 4 days of the window."""
    if len(window_counts) < 7:
        return "stable"
    recent = sum(window_counts[-3:]) / 3
    earlier = sum(window_counts[:-3]) / 4
    if earlier <= 0:
        return "up" if recent > 0 else "stable"
    ratio = recent / earlier
    if ratio >= 1.15:
        return "up"
    if ratio <= 0.85:
        return "down"
    return "stable"


def _confidence(contributor_count: int) -> str:
    if contributor_count >= 7:
        return "high"
    if contributor_count >= 4:
        return "medium"
    return "low"


def _aggregate(
    db: Session, window_start: date, window_end: date, baseline_days: int
) -> Tuple[List[Tuple[str, str, date, int]], Dict[Tuple[str, str], int]]:
    """Return daily aggregates and distinct contributor counts.

    This runs inside a tenant bypass because it is a deliberate cross-tenant
    aggregate. Only two projections are returned: daily totals and a count of
    contributors. No tenant identifier ever leaves this function.
    """
    baseline_start = window_start - timedelta(days=baseline_days)

    daily_rows = (
        db.query(
            models.Tenant.region_code,
            models.SurveillanceDailyCount.condition_name,
            models.SurveillanceDailyCount.count_date,
            func.sum(models.SurveillanceDailyCount.otc_units).label("total_units"),
        )
        .join(
            models.Tenant,
            models.SurveillanceDailyCount.tenant_id == models.Tenant.id,
        )
        .filter(
            models.Tenant.surveillance_opt_in.is_(True),
            models.Tenant.region_code.isnot(None),
            models.SurveillanceDailyCount.count_date >= baseline_start,
            models.SurveillanceDailyCount.count_date <= window_end,
        )
        .group_by(
            models.Tenant.region_code,
            models.SurveillanceDailyCount.condition_name,
            models.SurveillanceDailyCount.count_date,
        )
        .all()
    )

    contributor_rows = (
        db.query(
            models.Tenant.region_code,
            models.SurveillanceDailyCount.condition_name,
            func.count(func.distinct(models.SurveillanceDailyCount.tenant_id)).label("contributors"),
        )
        .join(
            models.Tenant,
            models.SurveillanceDailyCount.tenant_id == models.Tenant.id,
        )
        .filter(
            models.Tenant.surveillance_opt_in.is_(True),
            models.Tenant.region_code.isnot(None),
            models.SurveillanceDailyCount.count_date >= window_start,
            models.SurveillanceDailyCount.count_date <= window_end,
        )
        .group_by(
            models.Tenant.region_code,
            models.SurveillanceDailyCount.condition_name,
        )
        .all()
    )

    daily = [
        (row.region_code, row.condition_name, row.count_date, int(row.total_units or 0))
        for row in daily_rows
    ]
    contributors = {
        (row.region_code, row.condition_name): int(row.contributors or 0)
        for row in contributor_rows
    }
    return daily, contributors


def refresh_heatmap(
    db: Session,
    window_days: int = DEFAULT_WINDOW_DAYS,
    baseline_days: int = DEFAULT_BASELINE_DAYS,
) -> Dict[str, Any]:
    """Rebuild the latest k-anonymous heatmap snapshot. Idempotent by date."""
    if window_days < 3:
        raise ValueError("window_days must be at least 3")
    if baseline_days < 3:
        raise ValueError("baseline_days must be at least 3")

    window_end = date.today()
    window_start = window_end - timedelta(days=window_days - 1)
    computed_at = datetime.now(timezone.utc)

    with bypass_tenant_filter(db):
        daily, contributors = _aggregate(db, window_start, window_end, baseline_days)

        by_pair: Dict[Tuple[str, str], Dict[date, int]] = {}
        for region_code, condition_name, day, total in daily:
            by_pair.setdefault((region_code, condition_name), {})[day] = total

        published = 0
        suppressed = 0
        cells: List[dict] = []

        # Only pairs with data inside the current window are candidates. A
        # pair that appeared solely in the baseline must not inflate the
        # suppression count or create a stale cell.
        candidate_pairs = {
            pair for pair, day_map in by_pair.items()
            if any(window_start <= day <= window_end for day in day_map)
        }

        for pair in candidate_pairs:
            region_code, condition_name = pair
            day_map = by_pair[pair]
            contributor_count = contributors.get(pair, 0)

            # THE privacy rule: no cell below k contributors, ever.
            if contributor_count < HEATMAP_MIN_CONTRIBUTORS:
                suppressed += 1
                continue

            all_dates = [
                window_start - timedelta(days=i)
                for i in range(baseline_days, 0, -1)
            ] + [window_start + timedelta(days=i) for i in range(window_days)]

            series = [day_map.get(d, 0) for d in all_dates]
            window_counts = series[-window_days:]
            window_total = sum(window_counts)
            if window_total <= 0:
                continue

            z_map = anomaly_service._leave_one_out_zscores(series)
            window_indices = range(baseline_days, baseline_days + window_days)
            window_z = [z_map.get(i, 0.0) for i in window_indices]
            finite_z = [z for z in window_z if math.isfinite(z)]
            z_score = max(finite_z, default=0.0)
            if max(series) == min(series):
                z_score = 0.0

            signal_level = _classify_signal(z_score)
            trend = _classify_trend(window_counts)
            volume_band = _classify_volume(window_total)
            confidence = _confidence(contributor_count)
            trend_labels = [_classify_signal(z) for z in window_z]

            cell = {
                "region_code": region_code,
                "condition_name": condition_name,
                "signal_level": signal_level,
                "trend": trend,
                "trend_labels": trend_labels,
                "contributor_count": contributor_count,
                "public_volume_band": volume_band,
                "total_units": window_total,  # internal only, never in API DTO
                "z_score": round(float(z_score), 3),
                "confidence": confidence,
            }
            cell["payload_hash"] = _sha256(_canonical(cell))
            cells.append(cell)
            published += 1

        run_hash = _sha256(_canonical({
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "cells": [c["payload_hash"] for c in cells],
        }))

        run = (
            db.query(models.RegionHeatmapRun)
            .filter_by(window_start=window_start, window_end=window_end)
            .first()
        )
        if run is None:
            run = models.RegionHeatmapRun(
                window_start=window_start,
                window_end=window_end,
                window_days=window_days,
                published_cells=published,
                suppressed_cells=suppressed,
                regions_scanned=len({region for region, _ in candidate_pairs}),
                payload_hash=run_hash,
            )
            db.add(run)
            db.flush()
        else:
            run.window_days = window_days
            run.published_cells = published
            run.suppressed_cells = suppressed
            run.regions_scanned = len({region for region, _ in candidate_pairs})
            run.payload_hash = run_hash

        db.query(models.RegionHeatmapSnapshot).filter_by(run_id=run.id).delete(
            synchronize_session=False
        )
        for cell in cells:
            db.add(models.RegionHeatmapSnapshot(
                run_id=run.id,
                region_code=cell["region_code"],
                condition_name=cell["condition_name"],
                signal_level=cell["signal_level"],
                trend=cell["trend"],
                trend_labels_json=json.dumps(cell["trend_labels"]),
                contributor_count=cell["contributor_count"],
                public_volume_band=cell["public_volume_band"],
                total_units=cell["total_units"],
                z_score=Decimal(str(cell["z_score"])),
                confidence=cell["confidence"],
                payload_hash=cell["payload_hash"],
                computed_at=computed_at,
            ))

        db.commit()

    return {
        "status": "ok",
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "window_days": window_days,
        "published_cells": published,
        "suppressed_cells": suppressed,
        "regions_scanned": run.regions_scanned,
        "computed_at": computed_at.isoformat(),
    }


def _public_cell(snapshot: models.RegionHeatmapSnapshot) -> Dict[str, Any]:
    """The ONLY serialization path for heatmap cells. Never add raw units."""
    try:
        trend_labels = json.loads(snapshot.trend_labels_json or "[]")
    except (TypeError, ValueError):
        trend_labels = []
    return {
        "region_code": snapshot.region_code,
        "condition_name": snapshot.condition_name,
        "signal_level": snapshot.signal_level,
        "trend": snapshot.trend,
        "trend_labels": trend_labels,
        "contributor_count": snapshot.contributor_count,
        "public_volume_band": snapshot.public_volume_band,
        "confidence": snapshot.confidence,
        "privacy_safe": snapshot.contributor_count >= HEATMAP_MIN_CONTRIBUTORS,
    }


def get_heatmap(
    db: Session,
    condition_name: str = None,
    region_code: str = None,
) -> Dict[str, Any]:
    """Return the latest sanitized heatmap. Safe for public consumption."""
    latest = db.query(models.RegionHeatmapRun).order_by(
        models.RegionHeatmapRun.window_end.desc(),
        models.RegionHeatmapRun.id.desc(),
    ).first()
    if latest is None:
        return {
            "as_of": None,
            "window_start": None,
            "window_end": None,
            "window_days": DEFAULT_WINDOW_DAYS,
            "privacy": {
                "min_contributors": HEATMAP_MIN_CONTRIBUTORS,
                "aggregation": f"region_condition_{DEFAULT_WINDOW_DAYS}d",
                "individual_data_included": False,
            },
            "suppressed_cells": 0,
            "cells": [],
            "notice": "Public-health signal for awareness only; not a medical diagnosis.",
        }

    query = db.query(models.RegionHeatmapSnapshot).filter_by(run_id=latest.id)
    if condition_name:
        query = query.filter(models.RegionHeatmapSnapshot.condition_name == condition_name.strip().upper())
    if region_code:
        query = query.filter(models.RegionHeatmapSnapshot.region_code == region_code.strip().upper())

    snapshots = query.all()
    snapshots.sort(
        key=lambda s: (
            _SIGNAL_ORDER.get(s.signal_level, 0),
            _VOLUME_ORDER.get(s.public_volume_band, 0),
        ),
        reverse=True,
    )

    return {
        "as_of": latest.created_at.isoformat() if latest.created_at else None,
        "window_start": latest.window_start.isoformat(),
        "window_end": latest.window_end.isoformat(),
        "window_days": latest.window_days,
        "privacy": {
            "min_contributors": HEATMAP_MIN_CONTRIBUTORS,
            "aggregation": f"region_condition_{latest.window_days}d",
            "individual_data_included": False,
        },
        "suppressed_cells": latest.suppressed_cells,
        "cells": [_public_cell(s) for s in snapshots],
        "notice": "Public-health signal for awareness only; not a medical diagnosis.",
    }


def get_region_heatmap(db: Session, region_code: str) -> Dict[str, Any]:
    """Return one region's sanitized cells from the latest run."""
    result = get_heatmap(db, region_code=region_code)
    result["region_code"] = region_code.strip().upper()
    return result
