import pytest
from datetime import datetime, timedelta
from app.services import cold_chain_service
from app.models import ColdChainUnit, ColdChainReading, AuditLedgerEntry, MedicineBatch
from app.schemas import ColdChainReadingCreate, ColdChainUnitCreate, ColdChainUnitUpdate
from fastapi.testclient import TestClient

def test_create_and_list_units(db_session):
    u1 = cold_chain_service.create_unit(db_session, "Fridge A", "Front", 2.0, 8.0)
    assert u1.id is not None
    assert u1.unit_label == "Fridge A"

    u2 = cold_chain_service.create_unit(db_session, "Fridge B", "Back", 2.0, 8.0)
    units = cold_chain_service.list_units(db_session)
    assert len(units) >= 2
    labels = [u.unit_label for u in units]
    assert "Fridge A" in labels
    assert "Fridge B" in labels

def test_record_reading_normal(db_session, owner_user):
    unit = cold_chain_service.create_unit(db_session, "Test Fridge 1", "Room 1", 2.0, 8.0)
    reading = cold_chain_service.record_reading(db_session, unit.id, 5.0, owner_user.id)
    assert reading.recorded_temp_c == 5.0
    assert not reading.is_excursion
    assert reading.unit_id == unit.id

def test_record_reading_excursion(db_session, owner_user):
    unit = cold_chain_service.create_unit(db_session, "Test Fridge 2", "Room 1", 2.0, 8.0)
    reading = cold_chain_service.record_reading(db_session, unit.id, 10.0, owner_user.id)
    assert reading.is_excursion is True

def test_record_reading_audit(db_session, owner_user):
    unit = cold_chain_service.create_unit(db_session, "Test Fridge 3", "Room 1", 2.0, 8.0)
    reading = cold_chain_service.record_reading(db_session, unit.id, 4.0, owner_user.id)
    
    audit = db_session.query(AuditLedgerEntry).filter(AuditLedgerEntry.event_type == "cold_chain_reading", AuditLedgerEntry.reference_id == reading.id).first()
    assert audit is not None
    assert "4.0" in audit.payload_json

def test_compliance_report(db_session, owner_user):
    unit = cold_chain_service.create_unit(db_session, "Compliance Fridge", "Room 1", 2.0, 8.0)
    cold_chain_service.record_reading(db_session, unit.id, 5.0, owner_user.id)
    cold_chain_service.record_reading(db_session, unit.id, 4.0, owner_user.id)
    cold_chain_service.record_reading(db_session, unit.id, 10.0, owner_user.id) # 1 excursion out of 3

    report = cold_chain_service.get_compliance_report(db_session, unit.id, days=1)
    assert report["total_readings"] == 3
    assert report["excursion_count"] == 1
    # 2/3 compliant = 66.66%
    assert abs(report["compliance_pct"] - 66.66) < 0.1

def test_mark_batch_cold_chain(db_session, sample_medicine):
    batch = MedicineBatch(medicine_id=sample_medicine.id, qty_received=10)
    db_session.add(batch)
    db_session.commit()
    db_session.refresh(batch)

    updated = cold_chain_service.mark_batch_cold_chain(db_session, batch.id, True)
    assert updated.is_cold_chain is True

def test_api_access(client: TestClient, db_session, staff_headers, owner_headers):
    # Staff creates unit -> fails
    resp = client.post("/cold-chain/units", json={"unit_label": "API Fridge", "min_temp_c": 2.0, "max_temp_c": 8.0}, headers=staff_headers)
    assert resp.status_code == 403

    # Owner creates unit -> succeeds
    resp = client.post("/cold-chain/units", json={"unit_label": "API Fridge", "min_temp_c": 2.0, "max_temp_c": 8.0}, headers=owner_headers)
    assert resp.status_code == 200
    unit_id = resp.json()["id"]

    # Staff posts reading -> succeeds
    resp = client.post("/cold-chain/readings", json={"unit_id": unit_id, "recorded_temp_c": 4.5}, headers=staff_headers)
    assert resp.status_code == 200
    assert resp.json()["recorded_temp_c"] == 4.5
