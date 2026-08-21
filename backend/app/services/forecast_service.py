"""
Pillar 6, Part 1 - Demand Forecasting.

Extends the Smart Reorder Point Engine's flat 30-day average
(reorder_intelligence.py) with a genuinely seasonal forecast where
there's enough sales history to support one - a flat average treats
every day the same; a medicine that reliably sells more on weekends (or
around a local festival) doesn't get captured by that at all.

Library choice: statsmodels' Holt-Winters (ExponentialSmoothing) rather
than Prophet. Prophet is the more famous name, but it pulls in a heavy
Stan-based dependency that's genuinely painful to install/deploy for a
student project and offers little extra accuracy at this shop's data
volume; statsmodels ships pure-Python/NumPy, is well documented, and
Holt-Winters with weekly seasonality (seasonal_periods=7) is the right
level of sophistication for daily pharmacy sales data. This trade-off is
worth stating explicitly in the report - it's a deliberate engineering
decision, not a corner cut.

Honest degrading behaviour (the same "has_sufficient_data" pattern
already used by reorder_intelligence.compute_smart_threshold): a
seasonal model fit on too little/too flat data is worse than useless -
it can extrapolate confidently in a wrong direction. Below
MIN_HISTORY_DAYS of window or MIN_NONZERO_SALE_DAYS of actual sales
activity, OR if the model itself fails to fit (e.g. a near-constant
series statsmodels can't decompose seasonally), this falls back to a
flat historical daily average instead - always returns something useful,
never a silently overconfident forecast.

Directly reuses reorder_intelligence.compute_daily_sales_series() rather
than re-deriving a zero-filled daily series from Sale rows a second time.
"""
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app import models
from app.services.reorder_intelligence import compute_daily_sales_series

MIN_HISTORY_DAYS = 60
MIN_NONZERO_SALE_DAYS = 14


def _flat_average_forecast(series: list[float], history_days: int, periods: int) -> list[dict]:
    avg = sum(series) / history_days if history_days else 0.0
    today = date.today()
    return [
        {"date": (today + timedelta(days=i)).isoformat(), "predicted_qty": round(avg, 2)}
        for i in range(1, periods + 1)
    ]


def get_demand_forecast(db: Session, medicine_id: int, periods: int = 14, history_days: int = 180) -> dict:
    medicine = db.get(models.Medicine, medicine_id)
    if not medicine:
        raise ValueError(f"Medicine with id {medicine_id} not found")

    series = compute_daily_sales_series(db, medicine_id, window_days=history_days)
    nonzero_days = sum(1 for x in series if x > 0)

    if history_days < MIN_HISTORY_DAYS or nonzero_days < MIN_NONZERO_SALE_DAYS:
        return {
            "medicine_id": medicine.id, "medicine_name": medicine.particulars,
            "method": "flat_average", "has_sufficient_data": False,
            "history_days_used": history_days,
            "forecast": _flat_average_forecast(series, history_days, periods),
            "reason": (
                f"Only {nonzero_days} day(s) with sales activity in the last {history_days} days - "
                f"not enough history yet for a seasonal forecast. Showing a flat historical average instead."
            ),
        }

    try:
        import pandas as pd
        from statsmodels.tsa.holtwinters import ExponentialSmoothing

        today = date.today()
        idx = pd.date_range(end=today, periods=history_days, freq="D")
        s = pd.Series(series, index=idx)

        model = ExponentialSmoothing(
            s, trend="add", seasonal="add", seasonal_periods=7,
            initialization_method="estimated",
        )
        fit = model.fit(optimized=True)
        predictions = fit.forecast(periods).clip(lower=0)

        forecast = [
            {"date": d.date().isoformat(), "predicted_qty": round(float(v), 2)}
            for d, v in predictions.items()
        ]

        return {
            "medicine_id": medicine.id, "medicine_name": medicine.particulars,
            "method": "holt_winters", "has_sufficient_data": True,
            "history_days_used": history_days, "forecast": forecast, "reason": None,
        }

    except Exception as e:
        # Numerical failure (e.g. statsmodels can't fit a seasonal model
        # to a near-constant series) - degrade gracefully, never 500.
        return {
            "medicine_id": medicine.id, "medicine_name": medicine.particulars,
            "method": "flat_average_fallback", "has_sufficient_data": False,
            "history_days_used": history_days,
            "forecast": _flat_average_forecast(series, history_days, periods),
            "reason": f"Seasonal model could not be fit ({e}); showing a flat average instead.",
        }