"""
Unit and integration tests for reorder_intelligence.py
"""
import math
import pytest
from datetime import datetime, timedelta
from app import models
from app.config import settings
from app.services.reorder_intelligence import (
    compute_daily_sales_series,
    compute_smart_threshold,
    compute_smart_thresholds_bulk,
    apply_suggested_threshold,
)


def test_daily_sales_series_zero_fill(db_session, sample_medicine):
    today = datetime.utcnow().date()
    start_date = today - timedelta(days=29)

    # Sale on day 1 (start_date) and day 30 (today)
    sale1 = models.Sale(
        medicine_id=sample_medicine.id,
        qty_sold=5,
        sold_at=datetime.combine(start_date, datetime.min.time()),
    )
    sale2 = models.Sale(
        medicine_id=sample_medicine.id,
        qty_sold=10,
        sold_at=datetime.combine(today, datetime.min.time()),
    )
    db_session.add_all([sale1, sale2])
    db_session.commit()

    series = compute_daily_sales_series(db_session, sample_medicine.id, window_days=30)
    assert len(series) == 30
    assert series[0] == 5.0
    assert series[-1] == 10.0
    assert sum(series[1:-1]) == 0.0


def test_smart_threshold_hand_computed(db_session, sample_medicine):
    today = datetime.utcnow().date()
    # Construct 6 sale days in 30 days window: each 5 units sold
    # total = 30 units across 30 days -> avg = 1.0
    for i in range(6):
        d = today - timedelta(days=i * 2)
        s = models.Sale(
            medicine_id=sample_medicine.id,
            qty_sold=5,
            sold_at=datetime.combine(d, datetime.min.time()),
        )
        db_session.add(s)
    db_session.commit()

    res = compute_smart_threshold(db_session, sample_medicine.id, window_days=30)
    assert res["medicine_id"] == sample_medicine.id
    assert res["has_sufficient_data"] is True
    assert res["avg_daily_sales"] == 1.0
    assert res["total_units_sold_in_window"] == 30.0

    # Hand calculation:
    # avg = 1.0
    # 6 days have 5, 24 days have 0.
    # variance = (6*(5-1)^2 + 24*(0-1)^2) / 30 = (96 + 24) / 30 = 4.0
    # std_dev = sqrt(4.0) = 2.0
    # lead_time = 3 (default)
    # lead_time_demand = 1.0 * 3 = 3.0
    # safety_stock = 1.65 * 2.0 * sqrt(3) = 1.65 * 2.0 * 1.7320508 = 5.715767
    # raw = 3.0 + 5.715767 = 8.715767 -> ceil = 9
    assert res["std_dev_daily_sales"] == 2.0
    assert res["suggested_threshold"] == 9


def test_lead_time_override(db_session, sample_medicine):
    sample_medicine.lead_time_days = 5
    db_session.commit()

    today = datetime.utcnow().date()
    for i in range(6):
        d = today - timedelta(days=i * 2)
        s = models.Sale(
            medicine_id=sample_medicine.id,
            qty_sold=5,
            sold_at=datetime.combine(d, datetime.min.time()),
        )
        db_session.add(s)
    db_session.commit()

    res = compute_smart_threshold(db_session, sample_medicine.id, window_days=30)
    assert res["lead_time_days"] == 5


def test_insufficient_data_guardrail(db_session, sample_medicine):
    today = datetime.utcnow().date()
    # Only 1 sale in window
    s = models.Sale(
        medicine_id=sample_medicine.id,
        qty_sold=10,
        sold_at=datetime.combine(today, datetime.min.time()),
    )
    db_session.add(s)
    db_session.commit()

    res = compute_smart_threshold(db_session, sample_medicine.id, window_days=30)
    assert res["has_sufficient_data"] is False
    assert res["suggested_threshold"] is None
    assert "not enough history" in res["reason"]


def test_apply_suggested_threshold(db_session, sample_medicine):
    sample_medicine.suggested_low_stock_threshold = 15
    db_session.commit()

    med = apply_suggested_threshold(db_session, sample_medicine.id)
    assert med.low_stock_threshold == 15

    # Test error when no suggestion cached and insufficient data
    med2 = models.Medicine(particulars="NEW MED", normalized_name="NEW MED", current_stock=5)
    db_session.add(med2)
    db_session.commit()

    with pytest.raises(ValueError):
        apply_suggested_threshold(db_session, med2.id)


def test_api_lead_time_and_apply_flow(client, staff_headers, sample_medicine, db_session):
    # Staff token patch lead-time
    resp = client.patch(
        f"/stock/medicine/{sample_medicine.id}/lead-time",
        headers=staff_headers,
        json={"lead_time_days": 4},
    )
    assert resp.status_code == 200
    assert resp.json()["lead_time_days"] == 4

    # Record 6 sales for medicine so it gets sufficient data
    today = datetime.utcnow().date()
    for i in range(6):
        d = today - timedelta(days=i)
        s = models.Sale(
            medicine_id=sample_medicine.id,
            qty_sold=5,
            sold_at=datetime.combine(d, datetime.min.time()),
        )
        db_session.add(s)
    db_session.commit()

    # Apply smart threshold via API
    resp_apply = client.post(
        f"/stock/medicine/{sample_medicine.id}/smart-threshold/apply",
        headers=staff_headers,
    )
    assert resp_apply.status_code == 200
    applied_threshold = resp_apply.json()["low_stock_threshold"]
    assert applied_threshold is not None

    # Check that reorder list reflects the new threshold
    sample_medicine.current_stock = applied_threshold - 1
    db_session.commit()

    reorder_resp = client.get("/stock/reorder-list", headers=staff_headers)
    assert reorder_resp.status_code == 200
    groups = reorder_resp.json()
    all_items = [item for g in groups for item in g["items"]]
    matched = [i for i in all_items if i["medicine_id"] == sample_medicine.id]
    assert len(matched) == 1
    assert matched[0]["low_stock_threshold"] == applied_threshold
