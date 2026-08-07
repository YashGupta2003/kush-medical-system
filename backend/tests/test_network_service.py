"""Tests for network_service.py — Pillar 5, Part B (Inter-Pharmacy Network)."""
from datetime import date, timedelta

import pytest
from app.services import network_service, audit_service
from app import models


class TestNodes:
    def test_self_node_is_created_once_and_reused(self, db_session):
        n1 = network_service.get_or_create_self_node(db_session)
        db_session.commit()
        n2 = network_service.get_or_create_self_node(db_session)
        db_session.commit()
        assert n1.id == n2.id
        assert db_session.query(models.PharmacyNode).filter_by(is_self=True).count() == 1

    def test_add_node_creates_a_non_self_node(self, db_session):
        node = network_service.add_node(db_session, "Rathore Medicos Pharmacy", contact_phone="9998887770")
        assert node.is_self is False
        assert node.shop_name == "Rathore Medicos Pharmacy"

    def test_list_nodes_puts_self_first(self, db_session):
        network_service.get_or_create_self_node(db_session)
        db_session.commit()
        network_service.add_node(db_session, "Aadi Medicals")
        nodes = network_service.list_nodes(db_session)
        assert nodes[0].is_self is True


class TestListings:
    def test_create_manual_listing(self, db_session):
        self_node = network_service.get_or_create_self_node(db_session)
        db_session.commit()
        listing = network_service.create_manual_listing(
            db_session, self_node.id, "excess_stock", "Paracetamol 650mg", quantity=100,
        )
        assert listing.status == "open"
        assert listing.listing_type == "excess_stock"

    def test_list_listings_filters_by_status_and_type(self, db_session):
        self_node = network_service.get_or_create_self_node(db_session)
        db_session.commit()
        network_service.create_manual_listing(db_session, self_node.id, "excess_stock", "Item A", quantity=10)
        network_service.create_manual_listing(db_session, self_node.id, "shortage_request", "Item B", quantity=5)

        excess = network_service.list_listings(db_session, listing_type="excess_stock")
        assert len(excess) == 1
        assert excess[0].medicine_name == "Item A"

    def test_exclude_node_id_filters_out_own_listings(self, db_session):
        self_node = network_service.get_or_create_self_node(db_session)
        db_session.commit()
        other = network_service.add_node(db_session, "Other Pharmacy")
        network_service.create_manual_listing(db_session, self_node.id, "excess_stock", "Mine", quantity=1)
        network_service.create_manual_listing(db_session, other.id, "excess_stock", "Theirs", quantity=1)

        results = network_service.list_listings(db_session, exclude_node_id=self_node.id)
        names = [r.medicine_name for r in results]
        assert "Theirs" in names
        assert "Mine" not in names


class TestPublishNearExpiry:
    def test_publishes_critical_and_warning_batches(self, db_session, sample_medicine, sample_distributor):
        today = date.today()
        db_session.add(models.MedicineBatch(
            medicine_id=sample_medicine.id, expiry_date=today + timedelta(days=5),
            qty_received=20, distributor_id=sample_distributor.id,
        ))
        db_session.commit()

        listings = network_service.publish_near_expiry_listings(db_session, days=60)
        assert len(listings) == 1
        assert listings[0].listing_type == "near_expiry"
        assert listings[0].medicine_name == sample_medicine.particulars

    def test_expired_batches_are_never_published(self, db_session, sample_medicine, sample_distributor):
        today = date.today()
        db_session.add(models.MedicineBatch(
            medicine_id=sample_medicine.id, expiry_date=today - timedelta(days=5),
            qty_received=20, distributor_id=sample_distributor.id,
        ))
        db_session.commit()

        listings = network_service.publish_near_expiry_listings(db_session, days=60)
        assert listings == []

    def test_calling_twice_does_not_create_duplicate_listings(self, db_session, sample_medicine, sample_distributor):
        today = date.today()
        db_session.add(models.MedicineBatch(
            medicine_id=sample_medicine.id, expiry_date=today + timedelta(days=5),
            qty_received=20, distributor_id=sample_distributor.id,
        ))
        db_session.commit()

        first = network_service.publish_near_expiry_listings(db_session, days=60)
        second = network_service.publish_near_expiry_listings(db_session, days=60)
        assert len(first) == 1
        assert len(second) == 0   # already has an open listing for that batch


class TestClaimAndFulfill:
    def _open_listing(self, db_session):
        self_node = network_service.get_or_create_self_node(db_session)
        db_session.commit()
        return self_node, network_service.create_manual_listing(db_session, self_node.id, "excess_stock", "Test Item", quantity=10)

    def test_claim_by_different_node_succeeds(self, db_session):
        self_node, listing = self._open_listing(db_session)
        other = network_service.add_node(db_session, "Other Pharmacy")

        claimed = network_service.claim_listing(db_session, listing.id, other.id)
        assert claimed.status == "claimed"
        assert claimed.claimed_by_node_id == other.id

    def test_cannot_claim_own_listing(self, db_session):
        self_node, listing = self._open_listing(db_session)
        with pytest.raises(ValueError, match="cannot claim its own"):
            network_service.claim_listing(db_session, listing.id, self_node.id)

    def test_cannot_claim_already_claimed_listing(self, db_session):
        self_node, listing = self._open_listing(db_session)
        node_a = network_service.add_node(db_session, "Node A")
        node_b = network_service.add_node(db_session, "Node B")
        network_service.claim_listing(db_session, listing.id, node_a.id)

        with pytest.raises(ValueError, match="not open"):
            network_service.claim_listing(db_session, listing.id, node_b.id)

    def test_claim_logs_trustchain_entry(self, db_session):
        self_node, listing = self._open_listing(db_session)
        other = network_service.add_node(db_session, "Other Pharmacy")
        network_service.claim_listing(db_session, listing.id, other.id)

        entries = audit_service.get_ledger(db_session, event_type="network_transfer_claimed")
        assert len(entries) == 1

    def test_fulfill_requires_claimed_status_first(self, db_session):
        self_node, listing = self._open_listing(db_session)
        with pytest.raises(ValueError, match="not claimed"):
            network_service.fulfill_listing(db_session, listing.id)

    def test_fulfill_after_claim_succeeds_and_logs_trustchain(self, db_session):
        self_node, listing = self._open_listing(db_session)
        other = network_service.add_node(db_session, "Other Pharmacy")
        network_service.claim_listing(db_session, listing.id, other.id)

        fulfilled = network_service.fulfill_listing(db_session, listing.id)
        assert fulfilled.status == "fulfilled"

        entries = audit_service.get_ledger(db_session, event_type="network_transfer_fulfilled")
        assert len(entries) == 1

        report = audit_service.verify_chain(db_session)
        assert report["is_valid"] is True

    def test_withdraw_open_listing(self, db_session):
        self_node, listing = self._open_listing(db_session)
        withdrawn = network_service.withdraw_listing(db_session, listing.id)
        assert withdrawn.status == "withdrawn"

    def test_cannot_withdraw_a_claimed_listing(self, db_session):
        self_node, listing = self._open_listing(db_session)
        other = network_service.add_node(db_session, "Other Pharmacy")
        network_service.claim_listing(db_session, listing.id, other.id)

        with pytest.raises(ValueError, match="not open"):
            network_service.withdraw_listing(db_session, listing.id)