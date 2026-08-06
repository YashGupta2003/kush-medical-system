"""
Tests for audit_service.py — TrustChain's tamper-evident hash chain (Pillar 4).
"""
from app.services import audit_service
from app import models


def test_first_entry_chains_from_genesis(db_session):
    entry = audit_service.log_event(db_session, "rate_change", 1, {"old": 10, "new": 20})
    db_session.commit()

    assert entry.previous_hash == audit_service.GENESIS_HASH
    assert len(entry.entry_hash) == 64
    assert len(entry.payload_hash) == 64


def test_second_entry_chains_from_first(db_session):
    e1 = audit_service.log_event(db_session, "rate_change", 1, {"old": 10, "new": 20})
    db_session.commit()
    e2 = audit_service.log_event(db_session, "rate_change", 2, {"old": 20, "new": 30})
    db_session.commit()

    assert e2.previous_hash == e1.entry_hash
    assert e2.entry_hash != e1.entry_hash


def test_identical_payloads_still_produce_different_entry_hashes(db_session):
    """
    Two entries with the EXACT same payload must not produce the same
    entry_hash, because each chains from a different previous_hash - if
    this ever broke, reordering/duplicating entries would go undetected.
    """
    e1 = audit_service.log_event(db_session, "rate_change", 1, {"same": "payload"})
    db_session.commit()
    e2 = audit_service.log_event(db_session, "rate_change", 1, {"same": "payload"})
    db_session.commit()

    assert e1.payload_hash == e2.payload_hash   # same payload -> same payload_hash
    assert e1.entry_hash != e2.entry_hash        # but different position in the chain


def test_hash_is_independent_of_dict_key_order():
    h1 = audit_service._sha256(audit_service._canonical_json({"a": 1, "b": 2}))
    h2 = audit_service._sha256(audit_service._canonical_json({"b": 2, "a": 1}))
    assert h1 == h2


def test_verify_chain_reports_valid_for_untouched_chain(db_session):
    for i in range(5):
        audit_service.log_event(db_session, "rate_change", i, {"i": i})
        db_session.commit()

    report = audit_service.verify_chain(db_session)
    assert report["is_valid"] is True
    assert report["total_entries"] == 5
    assert report["broken_entries"] == []


def test_verify_chain_detects_payload_tampering(db_session):
    """
    Simulates someone editing an audit_ledger row directly in the database
    (bypassing audit_service.log_event entirely) - the whole point of the
    hash chain is that this becomes detectable.
    """
    e1 = audit_service.log_event(db_session, "rate_change", 1, {"old": 10, "new": 20})
    db_session.commit()
    audit_service.log_event(db_session, "rate_change", 2, {"old": 20, "new": 30})
    db_session.commit()

    row = db_session.query(models.AuditLedgerEntry).get(e1.id)
    row.payload_json = '{"old":10,"new":999999}'
    db_session.commit()

    report = audit_service.verify_chain(db_session)
    assert report["is_valid"] is False
    assert any(b["id"] == e1.id for b in report["broken_entries"])


def test_verify_chain_detects_entry_hash_tampering(db_session):
    e1 = audit_service.log_event(db_session, "rate_change", 1, {"old": 10, "new": 20})
    db_session.commit()

    row = db_session.query(models.AuditLedgerEntry).get(e1.id)
    row.entry_hash = "0" * 64
    db_session.commit()

    report = audit_service.verify_chain(db_session)
    assert report["is_valid"] is False
    assert report["broken_entries"][0]["id"] == e1.id


def test_verify_chain_detects_previous_hash_tampering(db_session):
    audit_service.log_event(db_session, "rate_change", 1, {"x": 1})
    db_session.commit()
    e2 = audit_service.log_event(db_session, "rate_change", 2, {"x": 2})
    db_session.commit()

    row = db_session.query(models.AuditLedgerEntry).get(e2.id)
    row.previous_hash = "f" * 64   # no longer chains from entry 1's actual hash
    db_session.commit()

    report = audit_service.verify_chain(db_session)
    assert report["is_valid"] is False
    assert any(b["id"] == e2.id for b in report["broken_entries"])


def test_get_ledger_filters_by_event_type(db_session):
    audit_service.log_event(db_session, "rate_change", 1, {"x": 1})
    db_session.commit()
    audit_service.log_event(db_session, "stock_adjustment", 2, {"x": 2})
    db_session.commit()

    rate_only = audit_service.get_ledger(db_session, event_type="rate_change")
    assert len(rate_only) == 1
    assert rate_only[0].event_type == "rate_change"


def test_get_ledger_returns_most_recent_first(db_session):
    audit_service.log_event(db_session, "rate_change", 1, {"x": 1})
    db_session.commit()
    e2 = audit_service.log_event(db_session, "rate_change", 2, {"x": 2})
    db_session.commit()

    ledger = audit_service.get_ledger(db_session)
    assert ledger[0].id == e2.id


def test_get_entries_for_reference(db_session):
    audit_service.log_event(db_session, "rate_change", 42, {"x": 1})
    db_session.commit()
    audit_service.log_event(db_session, "rate_change", 99, {"x": 2})
    db_session.commit()

    entries = audit_service.get_entries_for_reference(db_session, "rate_change", 42)
    assert len(entries) == 1
    assert entries[0].reference_id == 42


def test_empty_chain_verifies_as_valid(db_session):
    report = audit_service.verify_chain(db_session)
    assert report["is_valid"] is True
    assert report["total_entries"] == 0
    assert report["broken_entries"] == []