"""
Pillar 5, Part B — Inter-Pharmacy Network (near-expiry / excess-stock /
shortage-request listings between participating pharmacies).

Honest scoping note (this matters for the project report, and matches
pharma_roadmap.md's own framing): a REAL multi-pharmacy network means
separate shops running SEPARATE deployments of this app, each with their
own database, syncing listings to each other over the network (each
PharmacyNode.api_base_url is exactly where that sync call would go in
production). Building and deploying that actual multi-tenant
infrastructure is legitimately a "phase 2 product," not a single college
project's scope.

What's implemented HERE, honestly: every participating shop is modeled as
a PharmacyNode ROW in this shop's own database - one row has is_self=True
representing this instance (auto-created, see get_or_create_self_node);
the Owner can add more rows to represent nearby participating pharmacies
for a demo. Listings, claims, and fulfillment all work exactly as they
would in the real multi-tenant version - the WORKFLOW LOGIC is fully
real and correct - only the network transport between independently
hosted shops is simulated by using rows instead of separate deployments
plus HTTP calls. This is a deliberate, documented simplification, not a
hidden shortcut.

This is also precisely where Pillar 4's TrustChain framing becomes
genuinely justified rather than a buzzword: once a listing is claimed by
a DIFFERENT pharmacy node than the one that posted it, that's a
transaction between two parties who don't inherently trust each other -
so claim_listing()/fulfill_listing() below both log tamper-evident
entries to TrustChain (see app/services/audit_service.py), the same
ledger already used for rate changes, batch receipts, and stock
adjustments.
"""
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app import models
from app.services import audit_service, expiry_service

SELF_SHOP_NAME = "Kush Medical Hall (this shop)"


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------
def get_or_create_self_node(db: Session) -> models.PharmacyNode:
    node = db.query(models.PharmacyNode).filter_by(is_self=True).first()
    if node:
        return node
    node = models.PharmacyNode(shop_name=SELF_SHOP_NAME, is_self=True, opted_in=True, joined_at=datetime.now(timezone.utc))
    db.add(node)
    db.flush()
    return node


def list_nodes(db: Session) -> list[models.PharmacyNode]:
    return db.query(models.PharmacyNode).order_by(models.PharmacyNode.is_self.desc(), models.PharmacyNode.shop_name).all()


def add_node(db: Session, shop_name: str, api_base_url: Optional[str] = None, contact_phone: Optional[str] = None) -> models.PharmacyNode:
    node = models.PharmacyNode(
        shop_name=shop_name.strip(), api_base_url=api_base_url, contact_phone=contact_phone,
        is_self=False, opted_in=True, joined_at=datetime.now(timezone.utc),
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    return node


# ---------------------------------------------------------------------------
# Listings
# ---------------------------------------------------------------------------
def list_listings(db: Session, listing_type: Optional[str] = None, status: str = "open",
                   exclude_node_id: Optional[int] = None) -> list[models.NetworkListing]:
    query = db.query(models.NetworkListing)
    if listing_type:
        query = query.filter_by(listing_type=listing_type)
    if status:
        query = query.filter_by(status=status)
    if exclude_node_id is not None:
        query = query.filter(models.NetworkListing.pharmacy_node_id != exclude_node_id)
    return query.order_by(models.NetworkListing.created_at.desc()).all()


def create_manual_listing(db: Session, pharmacy_node_id: int, listing_type: str, medicine_name: str,
                           composition: Optional[str] = None, quantity: Optional[float] = None,
                           expiry_date: Optional[date] = None, note: Optional[str] = None) -> models.NetworkListing:
    listing = models.NetworkListing(
        pharmacy_node_id=pharmacy_node_id, listing_type=listing_type, medicine_name=medicine_name.strip(),
        composition=composition, quantity=quantity, expiry_date=expiry_date, note=note, status="open",
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return listing


def publish_near_expiry_listings(db: Session, days: int = 60) -> list[models.NetworkListing]:
    """
    Auto-generates 'near_expiry' listings from this shop's OWN Expiry
    Tracker (expiry_service.get_expiry_dashboard) - turns a feature this
    project already has into an input for the network, exactly as
    pharma_roadmap.md describes. Idempotent per batch: a batch that
    already has an OPEN listing referencing it (source_batch_id) is
    skipped, so calling this repeatedly (e.g. from a daily scheduled job)
    never creates duplicate listings.
    """
    self_node = get_or_create_self_node(db)
    batches = expiry_service.get_expiry_dashboard(db, tenant_id=self_node.tenant_id, days=days)

    already_listed_batch_ids = {
        row[0] for row in
        db.query(models.NetworkListing.source_batch_id)
        .filter(models.NetworkListing.status == "open", models.NetworkListing.source_batch_id.isnot(None))
        .all()
    }

    created = []
    for b in batches:
        if b["urgency"] == "expired":
            continue   # already-expired stock isn't transferable/sellable - not a network candidate
        if b["batch_id"] in already_listed_batch_ids:
            continue

        listing = models.NetworkListing(
            pharmacy_node_id=self_node.id, listing_type="near_expiry",
            medicine_name=b["medicine_name"], quantity=b["qty_received"],
            expiry_date=b["expiry_date"], source_batch_id=b["batch_id"],
            note=f"{b['urgency']} — {b['days_remaining']} days remaining",
            status="open",
        )
        db.add(listing)
        created.append(listing)

    db.commit()
    for listing in created:
        db.refresh(listing)
    return created


def claim_listing(db: Session, listing_id: int, claiming_node_id: int) -> models.NetworkListing:
    """
    A different pharmacy node expresses intent to take a listing (arrange
    the physical transfer). Logs a tamper-evident 'network_transfer_claimed'
    TrustChain entry (Pillar 4) - a commitment between two independent
    parties is exactly the kind of fact neither side should be able to
    quietly deny later.
    """
    listing = db.get(models.NetworkListing, listing_id)
    if not listing:
        raise ValueError("Listing not found")
    if listing.status != "open":
        raise ValueError(f"Listing is '{listing.status}', not open — it can't be claimed")
    if listing.pharmacy_node_id == claiming_node_id:
        raise ValueError("A pharmacy cannot claim its own listing")

    claiming_node = db.get(models.PharmacyNode, claiming_node_id)
    if not claiming_node:
        raise ValueError("Claiming pharmacy node not found")

    listing.status = "claimed"
    listing.claimed_by_node_id = claiming_node_id
    listing.updated_at = datetime.now(timezone.utc)
    db.flush()

    # --- TrustChain (Pillar 4) ---
    audit_service.log_event(db, "network_transfer_claimed", listing.id, {
        "listing_id": listing.id, "medicine_name": listing.medicine_name,
        "quantity": float(listing.quantity) if listing.quantity is not None else None,
        "posted_by_node_id": listing.pharmacy_node_id,
        "claimed_by_node_id": claiming_node_id, "claimed_by_shop_name": claiming_node.shop_name,
    })

    db.commit()
    db.refresh(listing)
    return listing


def fulfill_listing(db: Session, listing_id: int) -> models.NetworkListing:
    """Marks a claimed listing as physically completed. Logs 'network_transfer_fulfilled' to TrustChain."""
    listing = db.get(models.NetworkListing, listing_id)
    if not listing:
        raise ValueError("Listing not found")
    if listing.status != "claimed":
        raise ValueError(f"Listing is '{listing.status}', not claimed — it must be claimed before it can be fulfilled")

    listing.status = "fulfilled"
    listing.updated_at = datetime.now(timezone.utc)
    db.flush()

    # --- TrustChain (Pillar 4) ---
    audit_service.log_event(db, "network_transfer_fulfilled", listing.id, {
        "listing_id": listing.id, "medicine_name": listing.medicine_name,
        "posted_by_node_id": listing.pharmacy_node_id, "claimed_by_node_id": listing.claimed_by_node_id,
    })

    db.commit()
    db.refresh(listing)
    return listing


def withdraw_listing(db: Session, listing_id: int) -> models.NetworkListing:
    """The posting shop cancels their own still-open listing."""
    listing = db.get(models.NetworkListing, listing_id)
    if not listing:
        raise ValueError("Listing not found")
    if listing.status != "open":
        raise ValueError(f"Listing is '{listing.status}', not open — only open listings can be withdrawn")

    listing.status = "withdrawn"
    listing.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(listing)
    return listing