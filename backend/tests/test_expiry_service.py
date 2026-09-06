"""
Tests for expiry_service.py - batch creation on bill confirm, the
Expired/Critical/Warning/Upcoming urgency buckets, and the 'missing
expiry info' prompt flow.
"""
from datetime import date, timedelta

from app.services import expiry_service
from app import models


def _confirmed_item_with_exp(db_session, medicine, distributor, exp_date_str):
    bill = models.Bill(distributor_id=distributor.id, status="confirmed", year=2026, month=7)
    db_session.add(bill)
    db_session.flush()
    item = models.BillItem(
        bill_id=bill.id, medicine_id=medicine.id, raw_name="TEST ITEM",
        qty=5, rate=10, gst_pct=5, amount=52.5, exp_date=exp_date_str, batch="B123",
    )
    db_session.add(item)
    db_session.flush()
    return item


def test_creates_batch_with_correctly_parsed_expiry(db_session, sample_medicine, sample_distributor, tenant):
    item = _confirmed_item_with_exp(db_session, sample_medicine, sample_distributor, "6/27")
    expiry_service.create_batch_from_confirmed_item(db_session, item)
    db_session.commit()

    batch = db_session.query(models.MedicineBatch).filter_by(bill_item_id=item.id).first()
    assert batch is not None
    assert batch.expiry_date is not None
    assert batch.expiry_date == date(2027, 6, 30)
    assert batch.batch_no == "B123"
    assert float(batch.qty_received) == 5.0


def test_creates_batch_even_when_expiry_text_is_unreadable(db_session, sample_medicine, sample_distributor, tenant):
    """
    Real bills sometimes don't have a readable expiry (handwriting, OCR
    miss). The batch record must still be created - with a NULL expiry -
    so it shows up in 'missing expiry info' instead of vanishing entirely.
    """
    item = _confirmed_item_with_exp(db_session, sample_medicine, sample_distributor, "garbled unreadable text")
    expiry_service.create_batch_from_confirmed_item(db_session, item)
    db_session.commit()

    batch = db_session.query(models.MedicineBatch).filter_by(bill_item_id=item.id).first()
    assert batch is not None
    assert batch.expiry_date is None


def test_does_not_create_duplicate_batch_for_same_bill_item(db_session, sample_medicine, sample_distributor, tenant):
    item = _confirmed_item_with_exp(db_session, sample_medicine, sample_distributor, "6/27")
    expiry_service.create_batch_from_confirmed_item(db_session, item)
    expiry_service.create_batch_from_confirmed_item(db_session, item)  # called twice, e.g. accidental retry
    db_session.commit()

    batches = db_session.query(models.MedicineBatch).filter_by(bill_item_id=item.id).all()
    assert len(batches) == 1


def test_expiry_dashboard_buckets_by_urgency(db_session, sample_medicine, sample_distributor, tenant):
    today = date.today()
    for exp in (today - timedelta(days=5), today + timedelta(days=3), today + timedelta(days=60)):
        db_session.add(models.MedicineBatch(
            medicine_id=sample_medicine.id, expiry_date=exp, qty_received=1, tenant_id=tenant.id,
            distributor_id=sample_distributor.id,
        ))
    db_session.commit()

    dashboard = expiry_service.get_expiry_dashboard(db_session, tenant_id=tenant.id, days=90)
    urgencies = {b["urgency"] for b in dashboard}
    assert "expired" in urgencies
    assert "critical" in urgencies
    assert "upcoming" in urgencies


def test_dashboard_respects_the_days_window(db_session, sample_medicine, sample_distributor, tenant):
    today = date.today()
    far_future = today + timedelta(days=200)
    db_session.add(models.MedicineBatch(
        medicine_id=sample_medicine.id, expiry_date=far_future, qty_received=1, tenant_id=tenant.id,
        distributor_id=sample_distributor.id,
    ))
    db_session.commit()

    dashboard = expiry_service.get_expiry_dashboard(db_session, tenant_id=tenant.id, days=90)
    assert len(dashboard) == 0   # 200 days out, outside a 90-day window


def test_missing_expiry_batches_are_listed_for_manual_entry(db_session, sample_medicine, tenant):
    db_session.add(models.MedicineBatch(medicine_id=sample_medicine.id, expiry_date=None, qty_received=3, tenant_id=tenant.id))
    db_session.commit()

    missing = expiry_service.get_missing_expiry_batches(db_session, tenant_id=tenant.id)
    assert len(missing) == 1
    assert missing[0]["medicine_id"] == sample_medicine.id


def test_fill_missing_expiry_updates_the_batch(db_session, sample_medicine, tenant):
    batch = models.MedicineBatch(medicine_id=sample_medicine.id, expiry_date=None, qty_received=3, tenant_id=tenant.id)
    db_session.add(batch)
    db_session.commit()
    db_session.refresh(batch)

    ok = expiry_service.fill_missing_expiry(db_session, tenant.id, batch.id, date(2027, 12, 31))
    assert ok is True

    db_session.refresh(batch)
    assert batch.expiry_date == date(2027, 12, 31)
    # and it should no longer appear in the "missing" list
    assert batch.id not in [b["batch_id"] for b in expiry_service.get_missing_expiry_batches(db_session, tenant_id=tenant.id)]


def test_fill_missing_expiry_returns_false_for_nonexistent_batch(db_session, tenant):
    assert expiry_service.fill_missing_expiry(db_session, tenant.id, 999999, date(2027, 1, 1)) is False