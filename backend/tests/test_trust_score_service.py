import pytest
from app import models
from app.services import trust_score_service

from datetime import datetime

def _make_confirmed_bill_chain(db, distributor, medicine, batch_no, rate, qty=10):
    bill = models.Bill(
        distributor_id=distributor.id, 
        status="confirmed", 
        invoice_no=f"INV-{distributor.id}-{batch_no}", 
        uploaded_at=datetime.utcnow(),
        invoice_date=datetime.utcnow().date()
    )
    db.add(bill)
    db.commit()

    item = models.BillItem(
        bill_id=bill.id,
        medicine_id=medicine.id,
        raw_name=medicine.particulars,
        batch=batch_no,
        computed_cost_per_unit=rate,
        qty=qty,
        match_status="auto"
    )
    db.add(item)
    db.commit()

    batch = models.MedicineBatch(
        medicine_id=medicine.id,
        batch_no=batch_no,
        distributor_id=distributor.id,
        bill_item_id=item.id,
        qty_received=qty
    )
    db.add(batch)
    db.commit()
    return bill, item, batch

def test_batch_normalization_catches_ocr_noise(db_session, sample_medicine):
    d1 = models.Distributor(name="Distributor 1")
    d2 = models.Distributor(name="Distributor 2")
    db_session.add_all([d1, d2])
    db_session.commit()

    _make_confirmed_bill_chain(db_session, d1, sample_medicine, "B-1234 ", 50.0)
    _make_confirmed_bill_chain(db_session, d2, sample_medicine, "b-1234", 50.0)

    collisions = trust_score_service.detect_batch_collisions(db_session)
    assert len(collisions) == 1
    assert d1.id in collisions[0]["distributor_ids"]
    assert d2.id in collisions[0]["distributor_ids"]

def test_genuine_single_distributor_batch_no_collision(db_session, sample_medicine, sample_distributor):
    _make_confirmed_bill_chain(db_session, sample_distributor, sample_medicine, "BATCH1", 50.0)
    _make_confirmed_bill_chain(db_session, sample_distributor, sample_medicine, "BATCH1", 50.0)

    collisions = trust_score_service.detect_batch_collisions(db_session)
    assert len(collisions) == 0

def test_rate_consistency_identifies_outlier_distributor(db_session, sample_medicine):
    d1 = models.Distributor(name="D1")
    d2 = models.Distributor(name="D2")
    d3 = models.Distributor(name="D3")
    d4 = models.Distributor(name="D4")
    db_session.add_all([d1, d2, d3, d4])
    db_session.commit()

    _make_confirmed_bill_chain(db_session, d1, sample_medicine, "B1", 50.0)
    _make_confirmed_bill_chain(db_session, d2, sample_medicine, "B2", 52.0)
    _make_confirmed_bill_chain(db_session, d3, sample_medicine, "B3", 49.0)
    _make_confirmed_bill_chain(db_session, d4, sample_medicine, "B4", 10.0)  # suspiciously low

    result = trust_score_service.compute_rate_consistency(db_session, sample_medicine.id)
    assert result["has_sufficient_data"] is True
    
    outliers = [d for d in result["distributor_averages"] if d["is_outlier"]]
    assert len(outliers) > 0
    assert outliers[0]["distributor_id"] == d4.id
    assert outliers[0]["direction"] == "low"

def test_rate_consistency_insufficient_data_below_3_distributors(db_session, sample_medicine):
    d1 = models.Distributor(name="D1")
    d2 = models.Distributor(name="D2")
    db_session.add_all([d1, d2])
    db_session.commit()

    _make_confirmed_bill_chain(db_session, d1, sample_medicine, "B1", 50.0)
    _make_confirmed_bill_chain(db_session, d2, sample_medicine, "B2", 52.0)

    result = trust_score_service.compute_rate_consistency(db_session, sample_medicine.id)
    assert result["has_sufficient_data"] is False

def test_composite_score_collision_heavier_than_rate_outlier(db_session, sample_medicine):
    d_collision = models.Distributor(name="Collision Dist")
    d_other = models.Distributor(name="Other Dist")
    d_rate_outlier = models.Distributor(name="Rate Outlier")
    d_normal1 = models.Distributor(name="Normal 1")
    d_normal2 = models.Distributor(name="Normal 2")
    db_session.add_all([d_collision, d_other, d_rate_outlier, d_normal1, d_normal2])
    db_session.commit()

    # Collision scenario
    _make_confirmed_bill_chain(db_session, d_collision, sample_medicine, "COLLISION_BATCH", 50.0)
    _make_confirmed_bill_chain(db_session, d_other, sample_medicine, "COLLISION_BATCH", 50.0)

    # Rate outlier scenario
    _make_confirmed_bill_chain(db_session, d_rate_outlier, sample_medicine, "B_OUTLIER", 10.0)
    _make_confirmed_bill_chain(db_session, d_normal1, sample_medicine, "B_NORM1", 50.0)
    _make_confirmed_bill_chain(db_session, d_normal2, sample_medicine, "B_NORM2", 52.0)

    score_collision = trust_score_service.compute_trust_score(db_session, d_collision.id, sample_medicine.id)
    score_rate_outlier = trust_score_service.compute_trust_score(db_session, d_rate_outlier.id, sample_medicine.id)

    assert score_collision["score"] < score_rate_outlier["score"]

def test_confidence_reflects_data_volume(db_session, sample_medicine):
    d_low_vol = models.Distributor(name="Low Vol")
    d_high_vol = models.Distributor(name="High Vol")
    db_session.add_all([d_low_vol, d_high_vol])
    db_session.commit()

    _make_confirmed_bill_chain(db_session, d_low_vol, sample_medicine, "B1", 50.0)

    for i in range(5):
        _make_confirmed_bill_chain(db_session, d_high_vol, sample_medicine, f"H{i}", 50.0)
    
    score_low = trust_score_service.compute_trust_score(db_session, d_low_vol.id, sample_medicine.id)
    score_high = trust_score_service.compute_trust_score(db_session, d_high_vol.id, sample_medicine.id)

    assert score_low["confidence"] == "low"
    assert score_high["confidence"] == "high"
