"""
Tests for analytics_service.py - every business-intelligence aggregation
the Analytics Dashboard depends on.
"""
from datetime import date, datetime

from app.services import analytics_service
from app import models


def _confirmed_bill(db_session, distributor, year, month, total, tenant_id=1):
    bill = models.Bill(tenant_id=tenant_id, distributor_id=distributor.id, status="confirmed", year=year, month=month, total_amount=total)
    db_session.add(bill)
    db_session.commit()
    return bill


def test_monthly_spend_sums_only_confirmed_bills_for_the_month(db_session, sample_distributor, tenant):
    today = date.today()
    _confirmed_bill(db_session, sample_distributor, today.year, today.month, 500.0, tenant_id=tenant.id)
    _confirmed_bill(db_session, sample_distributor, today.year, today.month, 300.0)

    result = analytics_service.get_monthly_spend(db_session, tenant_id=tenant.id, months=1)
    assert len(result) == 1
    assert result[0]["total_spend"] == 800.0
    assert result[0]["year"] == today.year
    assert result[0]["month"] == today.month


def test_monthly_spend_returns_zero_for_months_with_no_bills(db_session, tenant):
    result = analytics_service.get_monthly_spend(db_session, tenant_id=tenant.id, months=3)
    assert len(result) == 3
    assert all(point["total_spend"] == 0.0 for point in result)


def test_pending_bills_are_excluded_from_spend(db_session, sample_distributor, tenant):
    today = date.today()
    bill = models.Bill(tenant_id=tenant.id, 
        distributor_id=sample_distributor.id, status="pending_review",
        year=today.year, month=today.month, total_amount=1000.0,
    )
    db_session.add(bill)
    db_session.commit()

    result = analytics_service.get_monthly_spend(db_session, tenant_id=tenant.id, months=1)
    assert result[0]["total_spend"] == 0.0


def test_distributor_breakdown_groups_and_sorts_by_spend(db_session, sample_distributor, tenant):
    today = date.today()
    other = models.Distributor(name="OTHER DIST", tenant_id=tenant.id)
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)

    _confirmed_bill(db_session, sample_distributor, today.year, today.month, 500.0, tenant_id=tenant.id)
    _confirmed_bill(db_session, other, today.year, today.month, 200.0, tenant_id=tenant.id)

    breakdown = analytics_service.get_distributor_breakdown(db_session, tenant_id=tenant.id, year=today.year, month=today.month)
    totals = {b["distributor_name"]: b["total_spend"] for b in breakdown}

    assert totals[sample_distributor.name] == 500.0
    assert totals["OTHER DIST"] == 200.0
    assert breakdown[0]["total_spend"] >= breakdown[-1]["total_spend"]  # sorted descending


def test_price_changes_computes_net_movement_over_the_window(db_session, sample_medicine, tenant):
    db_session.add(models.RateHistory(tenant_id=tenant.id, medicine_id=sample_medicine.id, old_net_rate=50, new_net_rate=60, changed_at=datetime.utcnow()))
    db_session.add(models.RateHistory(tenant_id=tenant.id, medicine_id=sample_medicine.id, old_net_rate=60, new_net_rate=75, changed_at=datetime.utcnow()))
    db_session.commit()

    changes = analytics_service.get_price_changes(db_session, tenant_id=tenant.id, days=90, limit=10)
    assert len(changes) == 1
    change = changes[0]
    assert change["old_rate"] == 50.0
    assert change["new_rate"] == 75.0
    assert change["pct_change"] == 50.0   # (75-50)/50 * 100


def test_price_changes_ignores_entries_outside_the_window(db_session, sample_medicine, tenant):
    old_timestamp = datetime(2020, 1, 1)
    db_session.add(models.RateHistory(tenant_id=tenant.id, medicine_id=sample_medicine.id, old_net_rate=50, new_net_rate=100, changed_at=old_timestamp))
    db_session.commit()

    changes = analytics_service.get_price_changes(db_session, tenant_id=tenant.id, days=30, limit=10)
    assert len(changes) == 0


def test_top_medicines_by_spend_orders_correctly(db_session, sample_medicine, sample_distributor, tenant):
    today = date.today()
    bill = models.Bill(tenant_id=tenant.id, distributor_id=sample_distributor.id, status="confirmed", year=today.year, month=today.month)
    db_session.add(bill)
    db_session.flush()
    item = models.BillItem(bill_id=bill.id, medicine_id=sample_medicine.id, raw_name="X", qty=1, amount=999.0)
    db_session.add(item)
    db_session.commit()

    top = analytics_service.get_top_medicines_by_spend(db_session, tenant.id, today.year, today.month, limit=5)
    assert len(top) == 1
    assert top[0]["medicine_id"] == sample_medicine.id
    assert top[0]["total_spend"] == 999.0


def test_top_selling_sums_quantities_from_sales(db_session, sample_medicine, tenant):
    db_session.add(models.Sale(tenant_id=tenant.id, medicine_id=sample_medicine.id, qty_sold=5, sold_at=datetime.utcnow()))
    db_session.add(models.Sale(tenant_id=tenant.id, medicine_id=sample_medicine.id, qty_sold=3, sold_at=datetime.utcnow()))
    db_session.commit()

    top = analytics_service.get_top_selling(db_session, tenant_id=tenant.id, days=30, limit=5)
    assert len(top) == 1
    assert top[0]["qty_sold"] == 8.0


def test_overview_integrates_bills_stock_and_expiry(db_session, sample_medicine, sample_distributor, tenant):
    """
    This is the key integration test: the overview aggregation must pull
    from every feature area, not just one - confirming the dashboard
    genuinely reflects the whole system's state.
    """
    today = date.today()
    _confirmed_bill(db_session, sample_distributor, today.year, today.month, 1000.0, tenant_id=tenant.id)

    overview = analytics_service.get_overview(db_session, tenant_id=tenant.id)
    assert overview["this_month_spend"] == 1000.0
    assert overview["confirmed_bills_this_month"] == 1
    assert overview["distributors_used_this_month"] == 1
    assert "low_stock_count" in overview       # from the Stock feature
    assert "expiring_critical" in overview     # from the Expiry feature
    assert "pending_review_count" in overview  # from the Bill review queue
    assert "stock_value" in overview