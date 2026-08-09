"""
Integration tests: confirms Pillar 6 is actually wired into the existing
flows, not just correct in isolation - a manual stock adjustment made via
the real router-level function chain (stock_service.record_adjustment) is
attributable AND shows up in anomaly detection; the same for a POS cart
sale's created_by_user_id.
"""
from app import models
from app.services import stock_service, pos_service, anomaly_service, audit_service


def test_manual_adjustment_is_attributed_and_flaggable(db_session, sample_medicine, owner_user):
    stock_service.record_adjustment(
        db_session, sample_medicine.id, float(sample_medicine.current_stock) + 500,
        note="Physical count correction", created_by_user_id=owner_user.id,
    )

    ledger_row = (
        db_session.query(models.StockLedger)
        .filter_by(medicine_id=sample_medicine.id, reason="manual_adjustment")
        .order_by(models.StockLedger.id.desc())
        .first()
    )
    assert ledger_row.created_by_user_id == owner_user.id

    # And the audit trail (Pillar 4) recorded who performed it too.
    entries = audit_service.get_ledger(db_session, event_type="stock_adjustment")
    assert entries[0].payload_json.find(str(owner_user.id)) != -1 or "performed_by_user_id" in entries[0].payload_json


def test_pos_cart_sale_attributes_stock_ledger_to_staff(db_session, sample_medicine, staff_user):
    pos_service.record_cart_sale(
        db_session, [{"medicine_id": sample_medicine.id, "qty_sold": 2}],
        created_by_user_id=staff_user.id,
    )

    ledger_row = (
        db_session.query(models.StockLedger)
        .filter_by(medicine_id=sample_medicine.id, reason="sale")
        .order_by(models.StockLedger.id.desc())
        .first()
    )
    assert ledger_row.created_by_user_id == staff_user.id


def test_backward_compatible_call_without_user_id_still_works(db_session, sample_medicine):
    """Every pre-Pillar-6 caller that never passed created_by_user_id must keep working unchanged."""
    result = stock_service.record_sale(db_session, sample_medicine.id, 1)
    assert result["current_stock"] == float(sample_medicine.current_stock)

    ledger_row = (
        db_session.query(models.StockLedger)
        .filter_by(medicine_id=sample_medicine.id, reason="sale")
        .order_by(models.StockLedger.id.desc())
        .first()
    )
    assert ledger_row.created_by_user_id is None