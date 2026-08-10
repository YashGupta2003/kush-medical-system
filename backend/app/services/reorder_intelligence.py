"""
Smart Reorder Point Engine service module.
Data-driven inventory reorder threshold calculation based on rolling sales history,
lead time demand, and safety stock.
"""
import math
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from app import models
from app.config import settings


def compute_daily_sales_series(db: Session, medicine_id: int, window_days: int = 30) -> List[float]:
    """
    Zero-filled daily units-sold series for the last `window_days` days, oldest first.
    """
    today = datetime.utcnow().date()
    start_date = today - timedelta(days=window_days - 1)

    sales = (
        db.query(
            func.date(models.Sale.sold_at).label("sale_date"),
            func.sum(models.Sale.qty_sold).label("total_qty"),
        )
        .filter(
            models.Sale.medicine_id == medicine_id,
            func.date(models.Sale.sold_at) >= start_date,
            func.date(models.Sale.sold_at) <= today,
        )
        .group_by(func.date(models.Sale.sold_at))
        .all()
    )

    daily_map = {}
    for s_date, qty in sales:
        date_key = str(s_date) if not isinstance(s_date, str) else s_date
        daily_map[date_key] = float(qty or 0.0)

    series = []
    for i in range(window_days):
        current = start_date + timedelta(days=i)
        current_str = str(current)
        series.append(daily_map.get(current_str, 0.0))

    return series


def compute_smart_threshold(
    db: Session,
    medicine_id: int,
    window_days: int = 30,
    min_sale_days: int = 5,
    min_total_units: float = 3.0,
) -> Dict[str, Any]:
    """
    Computes data-driven smart reorder threshold for a medicine.
    Formula:
        lead_time_demand = avg_daily_sales * lead_time_days
        safety_stock     = z_score * std_dev_of_daily_sales * sqrt(lead_time_days)
        reorder_point    = ceil(lead_time_demand + safety_stock)

    BUG FIX #7 — Seasonal Medicine Penalization:
    The original variance formula divided by `window_days` (the full 30-day
    window including zero-sales days), severely inflating std_dev for medicines
    that don't sell every day. A drug sold only on 3 days/week but consistently
    had its safety stock over-estimated because 4/7 zero-days were treated as
    "high variance" data points rather than expected silence.

    Fix: variance is computed over `active_sale_days` (days with qty > 0) only.
    This means a slow-moving medicine that sells 5 units on exactly the same
    3 days each week gets std_dev=0 (perfectly consistent), not a large number.
    avg_daily_sales still uses `window_days` as the denominator (correct, for
    overall demand rate), but variability is measured among active selling days.
    """
    medicine = db.query(models.Medicine).get(medicine_id)
    if not medicine:
        raise ValueError(f"Medicine with id {medicine_id} not found")

    lead_time_days = medicine.lead_time_days if medicine.lead_time_days is not None else settings.default_lead_time_days

    series = compute_daily_sales_series(db, medicine_id, window_days)
    total_units_sold = sum(series)
    sale_days = sum(1 for qty in series if qty > 0)

    # avg_daily_sales uses window_days (correct: measures overall demand rate)
    avg_daily_sales = total_units_sold / window_days

    # BUG FIX #7: Compute variance ONLY over active sale days to avoid
    # penalizing seasonal/slow-moving medicines with artificially high std_dev.
    # Filter to days where sales actually occurred, then measure dispersion
    # among those active days only.
    active_sales = [qty for qty in series if qty > 0]
    if len(active_sales) > 1:
        active_mean = sum(active_sales) / len(active_sales)
        variance = sum((x - active_mean) ** 2 for x in active_sales) / len(active_sales)
    else:
        # 0 or 1 active days: no meaningful variance can be computed
        variance = 0.0
    std_dev_daily_sales = math.sqrt(variance)

    has_sufficient_data = (sale_days >= min_sale_days) and (total_units_sold >= min_total_units)

    if has_sufficient_data:
        lead_time_demand = avg_daily_sales * lead_time_days
        safety_stock = settings.reorder_safety_z_score * std_dev_daily_sales * math.sqrt(lead_time_days)
        raw_threshold = lead_time_demand + safety_stock
        suggested_threshold = math.ceil(max(0.0, raw_threshold))
        reason = None
    else:
        suggested_threshold = None
        reason = (
            f"Only {sale_days} sales day(s) and {total_units_sold:.1f} unit(s) sold in the last "
            f"{window_days} days - not enough history for a reliable suggestion yet."
        )

    # Cache last-computed suggestion on the Medicine model
    medicine.avg_daily_sales_30d = round(avg_daily_sales, 2)
    medicine.suggested_low_stock_threshold = suggested_threshold
    medicine.suggestion_computed_at = datetime.utcnow()
    db.commit()

    return {
        "medicine_id": medicine.id,
        "medicine_name": medicine.particulars,
        "avg_daily_sales": round(avg_daily_sales, 2),
        "std_dev_daily_sales": round(std_dev_daily_sales, 2),
        "lead_time_days": lead_time_days,
        "window_days": window_days,
        "sale_days_in_window": sale_days,
        "total_units_sold_in_window": float(total_units_sold),
        "has_sufficient_data": has_sufficient_data,
        "suggested_threshold": suggested_threshold,
        "current_threshold": float(medicine.low_stock_threshold) if medicine.low_stock_threshold is not None else None,
        "reason": reason,
    }


def compute_smart_thresholds_bulk(
    db: Session,
    window_days: int = 30,
    min_sale_days: int = 5,
    min_total_units: float = 3.0,
) -> List[Dict[str, Any]]:
    """
    Computes smart thresholds in bulk for every medicine that has at least one Sale row ever,
    using grouped aggregate queries to avoid N+1 ORM query traps.
    """
    sale_med_ids = [m_id for (m_id,) in db.query(models.Sale.medicine_id).distinct().all()]
    if not sale_med_ids:
        return []

    medicines = db.query(models.Medicine).filter(models.Medicine.id.in_(sale_med_ids)).all()
    med_map = {m.id: m for m in medicines}

    today = datetime.utcnow().date()
    start_date = today - timedelta(days=window_days - 1)

    window_sales = (
        db.query(
            models.Sale.medicine_id,
            func.date(models.Sale.sold_at).label("sale_date"),
            func.sum(models.Sale.qty_sold).label("total_qty"),
        )
        .filter(
            models.Sale.medicine_id.in_(sale_med_ids),
            func.date(models.Sale.sold_at) >= start_date,
            func.date(models.Sale.sold_at) <= today,
        )
        .group_by(models.Sale.medicine_id, func.date(models.Sale.sold_at))
        .all()
    )

    sales_by_med: Dict[int, Dict[str, float]] = {m_id: {} for m_id in sale_med_ids}
    for m_id, s_date, qty in window_sales:
        d_str = str(s_date)
        sales_by_med[m_id][d_str] = float(qty or 0.0)

    results = []
    now = datetime.utcnow()

    for m_id in sale_med_ids:
        med = med_map.get(m_id)
        if not med:
            continue

        lead_time_days = med.lead_time_days if med.lead_time_days is not None else settings.default_lead_time_days

        med_daily = sales_by_med.get(m_id, {})
        series = []
        for i in range(window_days):
            c_date = str(start_date + timedelta(days=i))
            series.append(med_daily.get(c_date, 0.0))

        total_units_sold = sum(series)
        sale_days = sum(1 for q in series if q > 0)
        avg_daily_sales = total_units_sold / window_days
        # BUG FIX #7: Use active-sale-days variance to avoid penalizing seasonal medicines.
        # See compute_smart_threshold() for detailed explanation.
        active_sales = [q for q in series if q > 0]
        if len(active_sales) > 1:
            active_mean = sum(active_sales) / len(active_sales)
            variance = sum((x - active_mean) ** 2 for x in active_sales) / len(active_sales)
        else:
            variance = 0.0
        std_dev = math.sqrt(variance)

        has_sufficient_data = (sale_days >= min_sale_days) and (total_units_sold >= min_total_units)

        if has_sufficient_data:
            lead_time_demand = avg_daily_sales * lead_time_days
            safety_stock = settings.reorder_safety_z_score * std_dev * math.sqrt(lead_time_days)
            suggested_threshold = math.ceil(max(0.0, lead_time_demand + safety_stock))
            reason = None
        else:
            suggested_threshold = None
            reason = (
                f"Only {sale_days} sales day(s) and {total_units_sold:.1f} unit(s) sold in the last "
                f"{window_days} days - not enough history for a reliable suggestion yet."
            )

        med.avg_daily_sales_30d = round(avg_daily_sales, 2)
        med.suggested_low_stock_threshold = suggested_threshold
        med.suggestion_computed_at = now

        results.append({
            "medicine_id": med.id,
            "medicine_name": med.particulars,
            "avg_daily_sales": round(avg_daily_sales, 2),
            "std_dev_daily_sales": round(std_dev, 2),
            "lead_time_days": lead_time_days,
            "window_days": window_days,
            "sale_days_in_window": sale_days,
            "total_units_sold_in_window": float(total_units_sold),
            "has_sufficient_data": has_sufficient_data,
            "suggested_threshold": suggested_threshold,
            "current_threshold": float(med.low_stock_threshold) if med.low_stock_threshold is not None else None,
            "reason": reason,
        })

    db.commit()
    return results


def apply_suggested_threshold(db: Session, medicine_id: int) -> models.Medicine:
    """
    Explicit Owner action: copies medicine.suggested_low_stock_threshold into
    medicine.low_stock_threshold. Raises ValueError if no cached suggestion exists yet (triggers
    compute_smart_threshold inline first if needed).
    This is the ONLY function that writes to low_stock_threshold.
    """
    medicine = db.query(models.Medicine).get(medicine_id)
    if not medicine:
        raise ValueError(f"Medicine with id {medicine_id} not found")

    if medicine.suggested_low_stock_threshold is None:
        computed = compute_smart_threshold(db, medicine_id)
        if not computed.get("has_sufficient_data") or computed.get("suggested_threshold") is None:
            raise ValueError(
                computed.get("reason") or "No cached suggestion available for this medicine yet."
            )

    if medicine.suggested_low_stock_threshold is None:
        raise ValueError("No cached suggestion available for this medicine yet.")

    medicine.low_stock_threshold = medicine.suggested_low_stock_threshold
    db.commit()
    db.refresh(medicine)
    return medicine
