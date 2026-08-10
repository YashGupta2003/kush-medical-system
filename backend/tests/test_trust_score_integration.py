import pytest
from app import models
from app.services import trust_score_service, audit_service
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

def test_collision_produces_lowered_score_with_contributing_factors(db_session, sample_medicine):
    d1 = models.Distributor(name="Distributor A")
    d2 = models.Distributor(name="Distributor B")
    db_session.add_all([d1, d2])
    db_session.commit()

    _make_confirmed_bill_chain(db_session, d1, sample_medicine, "SAMEBATCH", 50.0)
    _make_confirmed_bill_chain(db_session, d2, sample_medicine, "SAMEBATCH", 50.0)

    result = trust_score_service.compute_trust_score(db_session, d1.id, sample_medicine.id)

    assert result["score"] < 100
    assert len(result["contributing_factors"]) > 0
    
    # Asserting the other distributor is named in factors
    factor_texts = str(result["contributing_factors"])
    assert "Distributor B" in factor_texts or str(d2.id) in factor_texts

def test_score_threshold_crossing_creates_trustchain_entry(db_session, sample_medicine):
    d1 = models.Distributor(name="Target Dist")
    d2 = models.Distributor(name="Other Dist 1")
    d3 = models.Distributor(name="Other Dist 2")
    d4 = models.Distributor(name="Normal Dist 1")
    d5 = models.Distributor(name="Normal Dist 2")
    db_session.add_all([d1, d2, d3, d4, d5])
    db_session.commit()

    # Pre-populate a previous high score
    old_score = models.DistributorTrustScore(
        distributor_id=d1.id,
        score=80,
        confidence="high",
        computed_at=datetime.utcnow()
    )
    db_session.add(old_score)
    db_session.commit()

    # Create multiple batch collisions to apply max batch penalty (-50, score -> 50)
    _make_confirmed_bill_chain(db_session, d1, sample_medicine, "COLLISION_1", 10.0)
    _make_confirmed_bill_chain(db_session, d2, sample_medicine, "COLLISION_1", 50.0)
    
    _make_confirmed_bill_chain(db_session, d1, sample_medicine, "COLLISION_2", 10.0)
    _make_confirmed_bill_chain(db_session, d3, sample_medicine, "COLLISION_2", 50.0)

    # Create rate outlier data: d1's rate (~10) is suspiciously low vs d4, d5 (~50)
    # Need 3+ total distributors for rate consistency to be meaningful
    _make_confirmed_bill_chain(db_session, d4, sample_medicine, "B_NORM1", 50.0)
    _make_confirmed_bill_chain(db_session, d5, sample_medicine, "B_NORM2", 52.0)

    # Call compute_trust_score — batch penalty (-50) + rate low outlier (-15) = score 35 < 40
    trust_score_service.compute_trust_score(db_session, d1.id)

    # Verify audit chain
    report = audit_service.verify_chain(db_session)
    assert report["is_valid"] is True
    
    entries = audit_service.get_ledger(db_session, event_type="distributor_trust_score_drop")
    assert len(entries) > 0

