"""
Unit tests for duplicate_service.py
"""
import pytest
from datetime import datetime
from app import models
from app.services.duplicate_service import normalize_invoice_no, find_confirmed_duplicate


def test_normalize_invoice_no():
    assert normalize_invoice_no("inv-123 ") == "INV-123"
    assert normalize_invoice_no("  INV-123  ") == "INV-123"
    assert normalize_invoice_no("") is None
    assert normalize_invoice_no("   ") is None
    assert normalize_invoice_no(None) is None


def test_find_confirmed_duplicate_basic(db_session, sample_distributor):
    # Bill 1 is confirmed
    bill1 = models.Bill(
        distributor_id=sample_distributor.id,
        invoice_no="INV-1001",
        status="confirmed",
        uploaded_at=datetime.utcnow(),
    )
    db_session.add(bill1)
    db_session.commit()

    # Search for duplicate
    dup = find_confirmed_duplicate(db_session, sample_distributor.id, "inv-1001")
    assert dup is not None
    assert dup.id == bill1.id

    # Exclude bill1
    dup_excluded = find_confirmed_duplicate(db_session, sample_distributor.id, "inv-1001", exclude_bill_id=bill1.id)
    assert dup_excluded is None


def test_different_distributor(db_session, sample_distributor):
    dist2 = models.Distributor(name="RATHORE MEDICOS")
    db_session.add(dist2)
    db_session.commit()

    bill1 = models.Bill(
        distributor_id=sample_distributor.id,
        invoice_no="INV-1001",
        status="confirmed",
    )
    db_session.add(bill1)
    db_session.commit()

    # Same invoice_no but different distributor -> not a duplicate
    dup = find_confirmed_duplicate(db_session, dist2.id, "INV-1001")
    assert dup is None


def test_unconfirmed_bill_not_duplicate(db_session, sample_distributor):
    bill1 = models.Bill(
        distributor_id=sample_distributor.id,
        invoice_no="INV-1001",
        status="pending_review",
    )
    db_session.add(bill1)
    db_session.commit()

    # Existing bill is only pending_review, not confirmed -> not a duplicate
    dup = find_confirmed_duplicate(db_session, sample_distributor.id, "INV-1001")
    assert dup is None


def test_blank_invoice_no_never_flagged(db_session, sample_distributor):
    bill1 = models.Bill(
        distributor_id=sample_distributor.id,
        invoice_no="",
        status="confirmed",
    )
    db_session.add(bill1)
    db_session.commit()

    assert find_confirmed_duplicate(db_session, sample_distributor.id, "") is None
    assert find_confirmed_duplicate(db_session, sample_distributor.id, None) is None
    assert find_confirmed_duplicate(db_session, None, "INV-1001") is None


def test_case_and_whitespace_insensitivity(db_session, sample_distributor):
    bill1 = models.Bill(
        distributor_id=sample_distributor.id,
        invoice_no="  inv-999  ",
        status="confirmed",
    )
    db_session.add(bill1)
    db_session.commit()

    dup = find_confirmed_duplicate(db_session, sample_distributor.id, "INV-999")
    assert dup is not None
    assert dup.id == bill1.id
