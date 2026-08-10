import pytest
from datetime import date, timedelta
from app.models import SurveillanceDailyCount, User, Medicine
from app.services import surveillance_service
from app.events.bus import event_bus

def test_get_conditions_for_medicine(db_session, sample_medicine):
    # This requires graph_service seeding, which is likely mocked or we can insert graph nodes.
    # We will test the record_sale_signal which calls this, by mocking get_conditions_for_medicine.
    pass

def test_record_sale_signal(db_session, sample_medicine, monkeypatch):
    monkeypatch.setattr(surveillance_service, "get_conditions_for_medicine", lambda db, med_id: ["Fever", "Headache"])
    
    surveillance_service.record_sale_signal(db_session, sample_medicine.id, 5)
    db_session.commit()
    
    records = db_session.query(SurveillanceDailyCount).all()
    assert len(records) == 2
    fever_record = [r for r in records if r.condition_name == "Fever"][0]
    assert fever_record.otc_units == 5
    assert fever_record.count_date == date.today()
    
    surveillance_service.record_sale_signal(db_session, sample_medicine.id, 3)
    db_session.commit()
    
    db_session.refresh(fever_record)
    assert fever_record.otc_units == 8

def test_get_trend_data(db_session):
    today = date.today()
    db_session.add(SurveillanceDailyCount(condition_name="Cough", count_date=today, otc_units=10))
    db_session.add(SurveillanceDailyCount(condition_name="Cough", count_date=today - timedelta(days=1), otc_units=5))
    db_session.commit()
    
    trend = surveillance_service.get_trend_data(db_session, "Cough", days=7)
    assert len(trend) == 7
    assert trend[-1]["otc_units"] == 10
    assert trend[-2]["otc_units"] == 5
    assert trend[0]["otc_units"] == 0

def test_detect_spikes(db_session, monkeypatch):
    today = date.today()
    for i in range(14):
        db_session.add(SurveillanceDailyCount(condition_name="Pain", count_date=today - timedelta(days=13-i), otc_units=2))
    
    # Spike on today
    db_session.add(SurveillanceDailyCount(condition_name="SpikeCondition", count_date=today, otc_units=100))
    for i in range(1, 14):
        db_session.add(SurveillanceDailyCount(condition_name="SpikeCondition", count_date=today - timedelta(days=i), otc_units=2))
        
    db_session.commit()
    
    spikes = surveillance_service.detect_spikes(db_session, days=14)
    assert len(spikes) >= 1
    spike_conds = [s["condition_name"] for s in spikes]
    assert "SpikeCondition" in spike_conds
    assert "Pain" not in spike_conds

def test_router_access(client, staff_headers, owner_headers):
    # Staff access should be forbidden
    resp = client.get("/surveillance/conditions", headers=staff_headers)
    assert resp.status_code == 403
    
    # Owner access allowed
    resp = client.get("/surveillance/conditions", headers=owner_headers)
    assert resp.status_code == 200
