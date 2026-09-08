import json
import pytest
from datetime import datetime
from app import models
from app.services.distributor_memory_service import (
    learn_from_confirmed_bill,
    get_template_for_distributor,
    match_header_row_against_template,
    get_field_accuracy_summary
)

def test_first_bill_creates_template(db_session, tenant, sample_distributor):
    headers = ["NAME", "PACK", "QTY", "RATE"]
    col_map = {"NAME": "name", "PACK": "pack", "QTY": "qty", "RATE": "rate"}
    corrections = {"name": False, "qty": True, "rate": False}
    
    learn_from_confirmed_bill(db_session, tenant.id, sample_distributor.id, headers, col_map, corrections)
    
    summary = get_field_accuracy_summary(db_session, tenant.id, sample_distributor.id)
    assert summary["sample_count"] == 1
    assert summary["status"] == "learning"
    assert summary["overall_confidence_pct"] == 66.67 # 1 out of 3 corrected = 2/3 correct

def test_second_bill_reinforces_template(db_session, tenant, sample_distributor):
    headers = ["NAME", "PACK", "QTY", "RATE"]
    col_map = {"NAME": "name", "PACK": "pack", "QTY": "qty", "RATE": "rate"}
    
    # First bill
    learn_from_confirmed_bill(db_session, tenant.id, sample_distributor.id, headers, col_map, {})
    
    # Second bill with slightly noisy header
    noisy_headers = ["NAME", "PCK", "QTY", "RATE"] 
    learn_from_confirmed_bill(db_session, tenant.id, sample_distributor.id, noisy_headers, col_map, {})
    
    summary = get_field_accuracy_summary(db_session, tenant.id, sample_distributor.id)
    assert summary["sample_count"] == 2
    
    # Ensure template was NOT overwritten
    template = get_template_for_distributor(db_session, tenant.id, sample_distributor.id)
    assert template["header_signature"] == headers

def test_five_bills_makes_confident(db_session, tenant, sample_distributor):
    headers = ["NAME"]
    col_map = {"NAME": "name"}
    
    for i in range(5):
        # 10 fields total, 1 corrected -> 90% confidence
        learn_from_confirmed_bill(db_session, tenant.id, sample_distributor.id, headers, col_map, {"name": False, "qty": i == 0})
        
    summary = get_field_accuracy_summary(db_session, tenant.id, sample_distributor.id)
    assert summary["sample_count"] == 5
    assert summary["status"] == "confident"
    assert summary["overall_confidence_pct"] == 90.0

def test_low_confidence_fields_flagged(db_session, tenant, sample_distributor):
    headers = ["NAME"]
    col_map = {"NAME": "name"}
    
    # 4 bills. 'name' is corrected 0 times (0%). 'qty' is corrected 2 times (50%). 'rate' is corrected 1 time (25%).
    for i in range(4):
        learn_from_confirmed_bill(db_session, tenant.id, sample_distributor.id, headers, col_map, {
            "name": False,
            "qty": i < 2,
            "rate": i == 0
        })
        
    summary = get_field_accuracy_summary(db_session, tenant.id, sample_distributor.id)
    assert "qty" in summary["low_confidence_fields"]
    assert "name" not in summary["low_confidence_fields"]
    assert "rate" not in summary["low_confidence_fields"]

def test_drifted_bill_replaces_template(db_session, tenant, sample_distributor):
    old_headers = ["NAME", "PACK", "QTY", "RATE"]
    col_map = {"NAME": "name"}
    learn_from_confirmed_bill(db_session, tenant.id, sample_distributor.id, old_headers, col_map, {})
    
    new_headers = ["ITEM_DESC", "BATCH", "EXP", "MRP"]
    learn_from_confirmed_bill(db_session, tenant.id, sample_distributor.id, new_headers, col_map, {})
    
    template = get_template_for_distributor(db_session, tenant.id, sample_distributor.id)
    assert template["sample_count"] == 1
    assert template["header_signature"] == new_headers

def test_match_header_row_logic():
    old = ["NAME", "PACK", "QTY", "RATE"]
    assert match_header_row_against_template(["NAME", "PACK", "QTY", "RATE"], old) is True
    assert match_header_row_against_template(["NAME", "PCK", "QTY", "RATE"], old) is True # typo
    assert match_header_row_against_template(["ITEM", "BATCH", "EXP", "MRP"], old) is False # drift

def test_no_bills_returns_not_learned(db_session, tenant, sample_distributor):
    summary = get_field_accuracy_summary(db_session, tenant.id, sample_distributor.id)
    assert summary["status"] == "not_learned"
    assert summary["overall_confidence_pct"] is None

def test_api_confidence_endpoint(client, db_session, tenant, sample_distributor, owner_headers):
    # Setup some data
    headers = ["NAME"]
    col_map = {"NAME": "name"}
    learn_from_confirmed_bill(db_session, tenant.id, sample_distributor.id, headers, col_map, {})
    
    response = client.get(f"/v1/trust-score/distributors/{sample_distributor.id}/confidence", headers=owner_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "learning"
    assert response.json()["sample_count"] == 1

def test_api_confidence_endpoint_404_cross_tenant(client, db_session, sample_distributor):
    tenant2 = models.Tenant(slug="test-shop-2", shop_name="Test Pharmacy 2", owner_name="Test Owner 2", email="t2@example.com")
    db_session.add(tenant2)
    db_session.commit()
    from app.services.auth_service import hash_password
    user2 = models.User(username="user2", password_hash=hash_password("pw"), full_name="User 2", role="owner", is_active=True, tenant_id=tenant2.id)
    db_session.add(user2)
    db_session.commit()
    from app.services.auth_service import create_access_token
    token = create_access_token(user2)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get(f"/v1/trust-score/distributors/{sample_distributor.id}/confidence", headers=headers)
    assert response.status_code == 404
