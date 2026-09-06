import pytest
import json
from datetime import datetime, timedelta, timezone
from app import models
from app.services import cross_tenant_integrity_service

def _setup_scenario(db_session, tenant1, tenant2, sample_medicine, batch_no):
    # Setup distributors
    d1 = models.Distributor(name="Dist A", tenant_id=tenant1.id)
    d2 = models.Distributor(name="Dist B", tenant_id=tenant2.id)
    db_session.add(d1)
    db_session.add(d2)
    db_session.flush()

    med2 = models.Medicine(particulars=sample_medicine.particulars, normalized_name=sample_medicine.normalized_name, tenant_id=tenant2.id)
    db_session.add(med2)
    db_session.flush()

    b1 = models.Bill(distributor_id=d1.id, tenant_id=tenant1.id, status="confirmed", invoice_date=datetime.now().date(), uploaded_at=datetime.now(timezone.utc))
    b2 = models.Bill(distributor_id=d2.id, tenant_id=tenant2.id, status="confirmed", invoice_date=datetime.now().date(), uploaded_at=datetime.now(timezone.utc))
    db_session.add(b1)
    db_session.add(b2)
    db_session.flush()

    i1 = models.BillItem(bill_id=b1.id, medicine_id=sample_medicine.id, batch=batch_no, raw_name="med")
    i2 = models.BillItem(bill_id=b2.id, medicine_id=med2.id, batch=batch_no, raw_name="med")
    db_session.add(i1)
    db_session.add(i2)
    db_session.commit()
    return d1, d2, b1, b2, med2

def test_detects_collision_across_two_tenants(db_session, tenant, sample_medicine):
    tenant2 = models.Tenant(slug="tenant2", shop_name="T2", owner_name="O2", email="t2@example.com", is_active=True)
    db_session.add(tenant2)
    db_session.flush()
    _setup_scenario(db_session, tenant, tenant2, sample_medicine, "BATCH123")

    result = cross_tenant_integrity_service.scan_cross_tenant_collisions(db_session)
    assert result["new_alerts"] == 1
    
    alerts = cross_tenant_integrity_service.get_alerts_for_tenant(db_session, tenant.id)
    assert len(alerts) == 1
    assert alerts[0]["normalized_batch_no"] == "BATCH123"
    assert alerts[0]["other_pharmacies_involved"] == 1

def test_single_tenant_same_batch_not_flagged(db_session, tenant, sample_medicine):
    d1 = models.Distributor(name="Dist A", tenant_id=tenant.id)
    d2 = models.Distributor(name="Dist B", tenant_id=tenant.id)
    db_session.add(d1)
    db_session.add(d2)
    db_session.flush()

    b1 = models.Bill(distributor_id=d1.id, tenant_id=tenant.id, status="confirmed", invoice_date=datetime.now().date(), uploaded_at=datetime.now(timezone.utc))
    b2 = models.Bill(distributor_id=d2.id, tenant_id=tenant.id, status="confirmed", invoice_date=datetime.now().date(), uploaded_at=datetime.now(timezone.utc))
    db_session.add(b1)
    db_session.add(b2)
    db_session.flush()

    i1 = models.BillItem(bill_id=b1.id, medicine_id=sample_medicine.id, batch="SINGLE123", raw_name="med")
    i2 = models.BillItem(bill_id=b2.id, medicine_id=sample_medicine.id, batch="SINGLE123", raw_name="med")
    db_session.add(i1)
    db_session.add(i2)
    db_session.commit()

    result = cross_tenant_integrity_service.scan_cross_tenant_collisions(db_session)
    assert result["new_alerts"] == 0

def test_two_tenants_same_batch_different_medicine_not_flagged(db_session, tenant, sample_medicine):
    tenant2 = models.Tenant(slug="tenant2", shop_name="T2", owner_name="O2", email="t2@example.com", is_active=True)
    db_session.add(tenant2)
    db_session.flush()

    d1 = models.Distributor(name="Dist A", tenant_id=tenant.id)
    d2 = models.Distributor(name="Dist B", tenant_id=tenant2.id)
    db_session.add(d1)
    db_session.add(d2)
    db_session.flush()

    med2 = models.Medicine(particulars="OTHER MED", normalized_name="OTHERMED", tenant_id=tenant2.id)
    db_session.add(med2)
    db_session.flush()

    b1 = models.Bill(distributor_id=d1.id, tenant_id=tenant.id, status="confirmed", invoice_date=datetime.now().date(), uploaded_at=datetime.now(timezone.utc))
    b2 = models.Bill(distributor_id=d2.id, tenant_id=tenant2.id, status="confirmed", invoice_date=datetime.now().date(), uploaded_at=datetime.now(timezone.utc))
    db_session.add(b1)
    db_session.add(b2)
    db_session.flush()

    i1 = models.BillItem(bill_id=b1.id, medicine_id=sample_medicine.id, batch="DIFFMED123", raw_name="med")
    i2 = models.BillItem(bill_id=b2.id, medicine_id=med2.id, batch="DIFFMED123", raw_name="othermed")
    db_session.add(i1)
    db_session.add(i2)
    db_session.commit()

    result = cross_tenant_integrity_service.scan_cross_tenant_collisions(db_session)
    assert result["new_alerts"] == 0

def test_rescan_updates_existing_does_not_duplicate(db_session, tenant, sample_medicine):
    tenant2 = models.Tenant(slug="tenant2", shop_name="T2", owner_name="O2", email="t2@example.com", is_active=True)
    db_session.add(tenant2)
    db_session.flush()
    _setup_scenario(db_session, tenant, tenant2, sample_medicine, "RESCAN123")

    r1 = cross_tenant_integrity_service.scan_cross_tenant_collisions(db_session)
    assert r1["new_alerts"] == 1
    
    # mark dismissed
    alerts = cross_tenant_integrity_service.get_alerts_for_tenant(db_session, tenant.id)
    cross_tenant_integrity_service.update_alert_status(db_session, alerts[0]["id"], tenant.id, "dismissed")
    
    r2 = cross_tenant_integrity_service.scan_cross_tenant_collisions(db_session)
    assert r2["new_alerts"] == 0
    assert r2["updated_alerts"] == 1
    
    # should still be dismissed
    alert = db_session.get(models.CrossTenantBatchAlert, alerts[0]["id"])
    assert alert.status == "dismissed"

def test_get_alerts_hides_other_tenants(db_session, tenant, sample_medicine):
    tenant2 = models.Tenant(slug="tenant2", shop_name="T2", owner_name="O2", email="t2@example.com", is_active=True)
    db_session.add(tenant2)
    db_session.flush()
    _setup_scenario(db_session, tenant, tenant2, sample_medicine, "HIDE123")
    cross_tenant_integrity_service.scan_cross_tenant_collisions(db_session)

    alerts = cross_tenant_integrity_service.get_alerts_for_tenant(db_session, tenant.id)
    assert "tenant_ids" not in alerts[0]
    assert alerts[0]["other_pharmacies_involved"] == 1

def test_update_status_raises_value_error_for_uninvolved_tenant(db_session, tenant, sample_medicine):
    tenant2 = models.Tenant(slug="tenant2", shop_name="T2", owner_name="O2", email="t2@example.com", is_active=True)
    db_session.add(tenant2)
    db_session.flush()
    _setup_scenario(db_session, tenant, tenant2, sample_medicine, "ERROR123")
    cross_tenant_integrity_service.scan_cross_tenant_collisions(db_session)

    alerts = cross_tenant_integrity_service.get_alerts_for_tenant(db_session, tenant.id)
    
    uninvolved_tenant_id = 999
    with pytest.raises(ValueError):
        cross_tenant_integrity_service.update_alert_status(db_session, alerts[0]["id"], uninvolved_tenant_id, "reviewed")
