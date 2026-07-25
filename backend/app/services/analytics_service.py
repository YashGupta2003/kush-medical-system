"""
All business-intelligence style aggregations, pulling from every part of
the system that already has real data: bills, rate_history, stock, sales,
medicine_batches. This is deliberately the one place that ties every
feature together into one dashboard - any NEW feature added later that
produces trackable numbers (a new ledger, a new event table, etc.) should
get a corresponding aggregation added here and surfaced on /analytics/overview,
so the dashboard keeps growing alongside the app instead of going stale.
"""
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_

from app import models


def _month_bounds(year: int, month: int):
    return year, month


def get_monthly_spend(db: Session, months: int = 6) -> list[dict]:
    """
    Total confirmed-bill spend per calendar month, most recent `months`
    months (including the current one). Powers the main trend chart.
    """
    today = date.today()
    # build the list of (year, month) we want, oldest first
    wanted = []
    y, m = today.year, today.month
    for _ in range(months):
        wanted.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    wanted.reverse()

    rows = (
        db.query(models.Bill.year, models.Bill.month, func.sum(models.Bill.total_amount))
        .filter(models.Bill.status == "confirmed")
        .group_by(models.Bill.year, models.Bill.month)
        .all()
    )
    spend_map = {(r[0], r[1]): float(r[2] or 0) for r in rows}

    return [
        {
            "year": yy, "month": mm,
            "label": date(yy, mm, 1).strftime("%b %Y"),
            "total_spend": spend_map.get((yy, mm), 0.0),
        }
        for yy, mm in wanted
    ]


def get_distributor_breakdown(db: Session, year: Optional[int] = None, month: Optional[int] = None) -> list[dict]:
    """
    'Is mahine kis distributor se sabse zyada khareeda' - defaults to the
    current calendar month if year/month aren't given.
    """
    today = date.today()
    year = year or today.year
    month = month or today.month

    rows = (
        db.query(
            models.Distributor.id, models.Distributor.name,
            func.sum(models.Bill.total_amount), func.count(models.Bill.id),
        )
        .join(models.Bill, models.Bill.distributor_id == models.Distributor.id)
        .filter(models.Bill.status == "confirmed", models.Bill.year == year, models.Bill.month == month)
        .group_by(models.Distributor.id, models.Distributor.name)
        .order_by(desc(func.sum(models.Bill.total_amount)))
        .all()
    )
    return [
        {"distributor_id": r[0], "distributor_name": r[1], "total_spend": float(r[2] or 0), "bill_count": r[3]}
        for r in rows
    ]


def get_price_changes(db: Session, days: int = 90, limit: int = 10) -> list[dict]:
    """
    'Kaunsi medicine ka price sabse zyada badha' - looks at every
    rate_history entry within the window, and for each medicine compares
    its EARLIEST old_net_rate to its LATEST new_net_rate in that window -
    i.e. the true net movement over the period, not just one single edit.
    """
    since = datetime.utcnow() - timedelta(days=days)
    history = (
        db.query(models.RateHistory)
        .filter(models.RateHistory.changed_at >= since)
        .filter(models.RateHistory.old_net_rate.isnot(None), models.RateHistory.new_net_rate.isnot(None))
        .order_by(models.RateHistory.medicine_id, models.RateHistory.changed_at.asc())
        .all()
    )

    by_medicine: dict[int, list[models.RateHistory]] = {}
    for h in history:
        by_medicine.setdefault(h.medicine_id, []).append(h)

    results = []
    for medicine_id, entries in by_medicine.items():
        baseline = float(entries[0].old_net_rate)
        final = float(entries[-1].new_net_rate)
        if baseline <= 0:
            continue
        pct_change = ((final - baseline) / baseline) * 100
        medicine = db.query(models.Medicine).get(medicine_id)
        if not medicine:
            continue
        results.append({
            "medicine_id": medicine_id,
            "medicine_name": medicine.particulars,
            "old_rate": baseline,
            "new_rate": final,
            "pct_change": round(pct_change, 1),
            "change_count": len(entries),
        })

    results.sort(key=lambda r: abs(r["pct_change"]), reverse=True)
    return results[:limit]


def get_top_medicines_by_spend(db: Session, year: Optional[int] = None, month: Optional[int] = None, limit: int = 10) -> list[dict]:
    """Which medicines cost the most cumulative money this period."""
    today = date.today()
    year = year or today.year
    month = month or today.month

    rows = (
        db.query(models.Medicine.id, models.Medicine.particulars, func.sum(models.BillItem.amount))
        .join(models.BillItem, models.BillItem.medicine_id == models.Medicine.id)
        .join(models.Bill, models.Bill.id == models.BillItem.bill_id)
        .filter(models.Bill.status == "confirmed", models.Bill.year == year, models.Bill.month == month)
        .group_by(models.Medicine.id, models.Medicine.particulars)
        .order_by(desc(func.sum(models.BillItem.amount)))
        .limit(limit)
        .all()
    )
    return [{"medicine_id": r[0], "medicine_name": r[1], "total_spend": float(r[2] or 0)} for r in rows]


def get_top_selling(db: Session, days: int = 30, limit: int = 10) -> list[dict]:
    """Top sellers by quantity, from the Sales table (the 'Record a Sale' feature)."""
    since = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(models.Medicine.id, models.Medicine.particulars, func.sum(models.Sale.qty_sold))
        .join(models.Sale, models.Sale.medicine_id == models.Medicine.id)
        .filter(models.Sale.sold_at >= since)
        .group_by(models.Medicine.id, models.Medicine.particulars)
        .order_by(desc(func.sum(models.Sale.qty_sold)))
        .limit(limit)
        .all()
    )
    return [{"medicine_id": r[0], "medicine_name": r[1], "qty_sold": float(r[2] or 0)} for r in rows]


def get_overview(db: Session) -> dict:
    """
    The single call that powers the top stat-card row - deliberately pulls
    from every feature area (bills, stock, expiry) so the dashboard reflects
    the whole system's current state at a glance.
    """
    today = date.today()
    this_year, this_month = today.year, today.month
    last_month_date = (date(this_year, this_month, 1) - timedelta(days=1))
    last_year, last_month = last_month_date.year, last_month_date.month

    def month_spend(y, m):
        total = (
            db.query(func.sum(models.Bill.total_amount))
            .filter(models.Bill.status == "confirmed", models.Bill.year == y, models.Bill.month == m)
            .scalar()
        )
        return float(total or 0)

    this_month_spend = month_spend(this_year, this_month)
    last_month_spend = month_spend(last_year, last_month)
    spend_change_pct = (
        ((this_month_spend - last_month_spend) / last_month_spend) * 100 if last_month_spend > 0 else None
    )

    confirmed_bills_this_month = (
        db.query(func.count(models.Bill.id))
        .filter(models.Bill.status == "confirmed", models.Bill.year == this_year, models.Bill.month == this_month)
        .scalar()
    )
    distributors_used_this_month = (
        db.query(func.count(func.distinct(models.Bill.distributor_id)))
        .filter(models.Bill.status == "confirmed", models.Bill.year == this_year, models.Bill.month == this_month,
                models.Bill.distributor_id.isnot(None))
        .scalar()
    )
    avg_bill_value = (this_month_spend / confirmed_bills_this_month) if confirmed_bills_this_month else 0.0

    # Stock value: sum(current_stock * net_rate) across all medicines - a
    # single number for "how much money is sitting on your shelves right now".
    stock_value = (
        db.query(func.sum(models.Medicine.current_stock * models.Medicine.net_rate))
        .filter(models.Medicine.net_rate.isnot(None))
        .scalar()
    )

    low_stock_count = (
        db.query(func.count(models.Medicine.id))
        .filter(models.Medicine.low_stock_threshold.isnot(None))
        .filter(models.Medicine.current_stock < models.Medicine.low_stock_threshold)
        .scalar()
    )

    pending_review_count = (
        db.query(func.count(models.Bill.id))
        .filter(models.Bill.status.in_(["pending_review", "needs_attention"]))
        .scalar()
    )

    # Reuses the expiry feature's own summary logic rather than duplicating it.
    from app.services import expiry_service
    expiry_summary = expiry_service.get_expiry_summary(db)

    return {
        "this_month_spend": this_month_spend,
        "last_month_spend": last_month_spend,
        "spend_change_pct": round(spend_change_pct, 1) if spend_change_pct is not None else None,
        "confirmed_bills_this_month": confirmed_bills_this_month or 0,
        "distributors_used_this_month": distributors_used_this_month or 0,
        "avg_bill_value": round(avg_bill_value, 2),
        "stock_value": round(float(stock_value or 0), 2),
        "low_stock_count": low_stock_count or 0,
        "pending_review_count": pending_review_count or 0,
        "expiring_critical": expiry_summary["critical"] + expiry_summary["expired"],
    }