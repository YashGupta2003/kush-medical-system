"""
Integration test: a Point-of-Sale cart sale on "credit" actually links the
Sale rows to the Customer AND charges the credit ledger the correct total
- i.e. Pillar 3 (cart sale + interaction check), Pillar 5 (customer/credit),
and Pillar 4 (TrustChain logging the charge) are genuinely wired together,
not just correct in isolation.
"""
from app.services import pos_service, customer_service, audit_service
from app import models


def test_credit_cart_sale_links_customer_and_charges_ledger(db_session, sample_medicine, tenant):
    customer = customer_service.get_or_create_customer(db_session, tenant_id=tenant.id, phone="9123456780", name="Udhaar Customer")
    db_session.commit()

    sample_medicine.mrp = 50.0
    db_session.commit()

    result = pos_service.record_cart_sale(
        db_session, tenant.id,
        [{"medicine_id": sample_medicine.id, "qty_sold": 3}],
        customer_id=customer.id,
        payment_mode="credit",
    )

    assert result["status"] == "recorded"
    assert result["payment_mode"] == "credit"
    assert result["total_value"] == 150.0
    assert result["credit_balance_after"] == 150.0

    # The underlying Sale row must actually be linked to the customer.
    sale = db_session.query(models.Sale).filter_by(medicine_id=sample_medicine.id).order_by(models.Sale.id.desc()).first()
    assert sale.customer_id == customer.id

    # And it must be tamper-evidently logged.
    entries = audit_service.get_ledger(db_session, event_type="credit_charge")
    assert len(entries) == 1


def test_cash_cart_sale_does_not_touch_credit_ledger(db_session, sample_medicine, tenant):
    customer = customer_service.get_or_create_customer(db_session, tenant_id=tenant.id, phone="9123456781", name="Cash Customer")
    db_session.commit()
    sample_medicine.mrp = 50.0
    db_session.commit()

    result = pos_service.record_cart_sale(
        db_session, tenant.id,
        [{"medicine_id": sample_medicine.id, "qty_sold": 2}],
        customer_id=customer.id,
        payment_mode="cash",
    )

    assert result["status"] == "recorded"
    assert result["credit_balance_after"] is None
    assert customer_service.get_customer_balance(db_session, customer.id) == 0


def test_walk_in_sale_with_no_customer_works_exactly_as_before(db_session, sample_medicine, tenant):
    """Backward-compatibility guard: omitting customer_id entirely must not break anything."""
    result = pos_service.record_cart_sale(db_session, tenant.id, [{"medicine_id": sample_medicine.id, "qty_sold": 1}])
    assert result["status"] == "recorded"
    assert result["credit_balance_after"] is None