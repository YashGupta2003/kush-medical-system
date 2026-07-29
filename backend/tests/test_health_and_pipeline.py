"""
Tests for Health Check endpoint and Duplicate Bill Protection.
"""
import pytest
from app.services.duplicate_checker import compute_file_checksum, check_duplicate_bill
from app import models


def test_health_check_endpoint(client):
    response = client.get("/health")
    assert response.status_code in (200, 503)
    data = response.json()
    assert "status" in data
    assert "services" in data
    assert "database" in data["services"]


def test_duplicate_checksum_calculation():
    data = b"sample bill image bytes"
    checksum1 = compute_file_checksum(data)
    checksum2 = compute_file_checksum(data)
    assert checksum1 == checksum2
    assert len(checksum1) == 64


def test_duplicate_bill_detection(db_session):
    content = b"invoice content binary"
    checksum = compute_file_checksum(content)

    bill = models.Bill(
        invoice_no="INV-9999",
        status="confirmed",
        checksum=checksum,
    )
    db_session.add(bill)
    db_session.commit()

    is_dup, reason, dup_bill = check_duplicate_bill(
        db_session, file_bytes=content, invoice_no="INV-9999"
    )
    assert is_dup is True
    assert dup_bill.id == bill.id
