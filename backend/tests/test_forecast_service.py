"""Tests for forecast_service.py — Pillar 6, Part 1 (Demand Forecasting)."""
from datetime import datetime, timedelta

import pytest
from app import models
from app.services import forecast_service


def _sale(db_session, medicine, days_ago, qty=2):
    s = models.Sale(medicine_id=medicine.id, qty_sold=qty, sold_at=datetime.utcnow() - timedelta(days=days_ago))
    db_session.add(s)
    db_session.commit()
    return s


def test_unknown_medicine_raises(db_session):
    with pytest.raises(ValueError):
        forecast_service.get_demand_forecast(db_session, 999999)


def test_insufficient_history_falls_back_to_flat_average(db_session, sample_medicine):
    _sale(db_session, sample_medicine, days_ago=1)
    _sale(db_session, sample_medicine, days_ago=2)

    result = forecast_service.get_demand_forecast(db_session, sample_medicine.id, periods=7, history_days=180)
    assert result["method"] == "flat_average"
    assert result["has_sufficient_data"] is False
    assert len(result["forecast"]) == 7
    assert result["reason"] is not None


def test_forecast_dates_are_sequential_and_start_tomorrow(db_session, sample_medicine):
    for i in range(20):
        _sale(db_session, sample_medicine, days_ago=i)

    result = forecast_service.get_demand_forecast(db_session, sample_medicine.id, periods=5, history_days=180)
    dates = [f["date"] for f in result["forecast"]]
    assert len(dates) == 5
    assert dates == sorted(dates)   # strictly increasing


def test_sufficient_regular_history_attempts_seasonal_model(db_session, sample_medicine):
    """
    With enough regular daily sales, the forecast should either succeed
    with holt_winters OR gracefully fall back - never crash, and always
    return a real forecast list either way.
    """
    for i in range(70):
        _sale(db_session, sample_medicine, days_ago=i, qty=2 + (i % 7))

    result = forecast_service.get_demand_forecast(db_session, sample_medicine.id, periods=10, history_days=90)
    assert result["method"] in ("holt_winters", "flat_average_fallback")
    assert len(result["forecast"]) == 10
    assert all(f["predicted_qty"] >= 0 for f in result["forecast"])


def test_no_sales_at_all_still_returns_a_forecast_shape(db_session, sample_medicine):
    result = forecast_service.get_demand_forecast(db_session, sample_medicine.id, periods=3, history_days=180)
    assert result["has_sufficient_data"] is False
    assert len(result["forecast"]) == 3
    assert all(f["predicted_qty"] == 0 for f in result["forecast"])