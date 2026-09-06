"""Tests for customer_service.py — Pillar 5, Part A."""
from datetime import datetime, timedelta

import pytest
from app.services import customer_service, audit_service
from app import models


def _consented_customer(db_session, tenant, phone="9999900001", name="Test Customer"):
    c = customer_service.get_or_create_customer(db_session, tenant_id=tenant.id, phone=phone, name=name, consented=True)
    db_session.commit()
    return c


def _sale(db_session, medicine, customer, days_ago):
    sale = models.Sale(
        medicine_id=medicine.id, customer_id=customer.id, qty_sold=1,
        sold_at=datetime.utcnow() - timedelta(days=days_ago),
    )
    db_session.add(sale)
    db_session.commit()
    return sale


class TestProfiles:
    def test_creates_new_customer_by_phone(self, db_session, tenant):
        c = customer_service.get_or_create_customer(db_session, tenant_id=tenant.id, phone="9876543210", name="Ramesh")
        db_session.commit()
        assert c.phone == "9876543210"
        assert c.name == "Ramesh"
        assert c.consent_given_at is None

    def test_same_phone_returns_existing_customer_not_a_duplicate(self, db_session, tenant):
        c1 = customer_service.get_or_create_customer(db_session, tenant_id=tenant.id, phone="9876543210", name="Ramesh")
        db_session.commit()
        c2 = customer_service.get_or_create_customer(db_session, tenant_id=tenant.id, phone="9876543210")
        db_session.commit()
        assert c1.id == c2.id
        assert db_session.query(models.Customer).count() == 1

    def test_consent_can_be_added_on_a_later_call(self, db_session, tenant):
        c = customer_service.get_or_create_customer(db_session, tenant_id=tenant.id, phone="9876543210")
        db_session.commit()
        assert c.consent_given_at is None
        customer_service.get_or_create_customer(db_session, tenant_id=tenant.id, phone="9876543210", consented=True)
        db_session.commit()
        db_session.refresh(c)
        assert c.consent_given_at is not None

    def test_search_matches_phone_or_name(self, db_session, tenant):
        customer_service.get_or_create_customer(db_session, tenant_id=tenant.id, phone="9111122223", name="Sharma Ji")
        db_session.commit()
        assert len(customer_service.search_customers(db_session, tenant_id=tenant.id, q="Sharma")) == 1
        assert len(customer_service.search_customers(db_session, tenant_id=tenant.id, q="91111")) == 1
        assert len(customer_service.search_customers(db_session, tenant_id=tenant.id, q="nomatch")) == 0


class TestCreditLedger:
    def test_new_customer_has_zero_balance(self, db_session, tenant):
        c = _consented_customer(db_session, tenant=tenant)
        assert customer_service.get_customer_balance(db_session, c.id) == 0

    def test_charge_credit_increases_balance(self, db_session, tenant):
        c = _consented_customer(db_session, tenant=tenant)
        result = customer_service.charge_credit(db_session, c.id, 250.0, note="udhaar for cough syrup", tenant_id=tenant.id)
        assert result["resulting_balance"] == 250.0

    def test_payment_reduces_balance(self, db_session, tenant):
        c = _consented_customer(db_session, tenant=tenant)
        customer_service.charge_credit(db_session, c.id, 500.0, tenant_id=tenant.id)
        result = customer_service.record_payment(db_session, c.id, 200.0, tenant_id=tenant.id)
        assert result["resulting_balance"] == 300.0

    def test_balance_is_running_total_across_many_entries(self, db_session, tenant):
        c = _consented_customer(db_session, tenant=tenant)
        customer_service.charge_credit(db_session, c.id, 100.0, tenant_id=tenant.id)
        customer_service.charge_credit(db_session, c.id, 50.0, tenant_id=tenant.id)
        customer_service.record_payment(db_session, c.id, 30.0, tenant_id=tenant.id)
        assert customer_service.get_customer_balance(db_session, c.id) == 120.0

    def test_charge_zero_or_negative_rejected(self, db_session, tenant):
        c = _consented_customer(db_session, tenant=tenant)
        with pytest.raises(ValueError):
            customer_service.charge_credit(db_session, c.id, 0, tenant_id=tenant.id)
        with pytest.raises(ValueError):
            customer_service.charge_credit(db_session, c.id, -10, tenant_id=tenant.id)

    def test_credit_events_are_logged_to_trustchain(self, db_session, tenant):
        c = _consented_customer(db_session, tenant=tenant)
        customer_service.charge_credit(db_session, c.id, 100.0, tenant_id=tenant.id)
        customer_service.record_payment(db_session, c.id, 40.0, tenant_id=tenant.id)

        charges = audit_service.get_ledger(db_session, event_type="credit_charge")
        payments = audit_service.get_ledger(db_session, event_type="credit_payment")
        assert len(charges) == 1
        assert len(payments) == 1

        report = audit_service.verify_chain(db_session)
        assert report["is_valid"] is True

    def test_outstanding_balances_only_lists_positive_balances(self, db_session, tenant):
        c1 = _consented_customer(db_session, tenant=tenant, phone="9000000001", name="Owes Money")
        c2 = _consented_customer(db_session, tenant=tenant, phone="9000000002", name="All Paid Up")
        customer_service.charge_credit(db_session, c1.id, 100.0, tenant_id=tenant.id)
        customer_service.charge_credit(db_session, c2.id, 50.0, tenant_id=tenant.id)
        customer_service.record_payment(db_session, c2.id, 50.0, tenant_id=tenant.id)

        outstanding = customer_service.list_customers_with_outstanding_balance(db_session, tenant.id)
        names = [o["name"] for o in outstanding]
        assert "Owes Money" in names
        assert "All Paid Up" not in names

    def test_get_credit_ledger_returns_entries_newest_first(self, db_session, tenant):
        c = _consented_customer(db_session, tenant=tenant)
        customer_service.charge_credit(db_session, c.id, 100.0, tenant_id=tenant.id)
        customer_service.charge_credit(db_session, c.id, 50.0, tenant_id=tenant.id)
        ledger = customer_service.get_credit_ledger(db_session, c.id)
        assert len(ledger) == 2
        assert ledger[0].change_amount == 50.0


class TestAdherenceAlerts:
    def test_regular_28_day_pattern_flags_overdue_after_50_days(self, db_session, sample_medicine, tenant):
        c = _consented_customer(db_session, tenant=tenant)
        # purchases at 84, 56, 28 days ago -> avg gap 28 days, last purchase 28 days ago is NOT yet overdue by itself,
        # so push the most recent purchase further back to simulate a missed refill.
        _sale(db_session, sample_medicine, c, days_ago=84)
        _sale(db_session, sample_medicine, c, days_ago=56)
        _sale(db_session, sample_medicine, c, days_ago=50)  # last purchase 50 days ago, avg gap ~17-28 days -> overdue

        alerts = customer_service.compute_adherence_alerts(db_session, customer_id=c.id)
        assert len(alerts) == 1
        assert alerts[0]["medicine_id"] == sample_medicine.id
        assert alerts[0]["days_overdue"] > 0

    def test_customer_still_within_their_usual_gap_is_not_flagged(self, db_session, sample_medicine, tenant):
        c = _consented_customer(db_session, tenant=tenant)
        _sale(db_session, sample_medicine, c, days_ago=60)
        _sale(db_session, sample_medicine, c, days_ago=30)  # ~30 day gap, last purchase 30 days ago - well within 1.5x

        alerts = customer_service.compute_adherence_alerts(db_session, customer_id=c.id)
        assert alerts == []

    def test_single_purchase_never_flagged(self, db_session, sample_medicine, tenant):
        c = _consented_customer(db_session, tenant=tenant)
        _sale(db_session, sample_medicine, c, days_ago=200)
        assert customer_service.compute_adherence_alerts(db_session, customer_id=c.id) == []

    def test_non_consented_customer_is_excluded_entirely(self, db_session, sample_medicine, tenant):
        c = customer_service.get_or_create_customer(db_session, tenant_id=tenant.id, phone="9333344445", consented=False)
        db_session.commit()
        _sale(db_session, sample_medicine, c, days_ago=84)
        _sale(db_session, sample_medicine, c, days_ago=56)
        _sale(db_session, sample_medicine, c, days_ago=50)

        assert customer_service.compute_adherence_alerts(db_session, customer_id=c.id) == []

    def test_very_frequent_repeat_purchases_are_not_treated_as_a_refill_cycle(self, db_session, sample_medicine, tenant):
        """
        Buying the same OTC item twice in the same week (e.g. for two
        different family members) is not a chronic refill pattern - the
        MIN_AVG_GAP_DAYS floor exists specifically to avoid flagging this.
        """
        c = _consented_customer(db_session, tenant=tenant)
        _sale(db_session, sample_medicine, c, days_ago=10)
        _sale(db_session, sample_medicine, c, days_ago=3)

        assert customer_service.compute_adherence_alerts(db_session, customer_id=c.id) == []