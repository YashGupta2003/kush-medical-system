"""
Inter-Pharmacy Network endpoints (Pillar 5, Part B). Node management
(registering participating pharmacies) is Owner-only, matching the
Staff/Users admin pattern already used elsewhere - listings themselves
(browsing, posting excess stock, claiming, fulfilling) are operational
and available to any logged-in staff member. See
app/services/network_service.py's module docstring for the honest
scoping note on how multi-shop participation is modeled.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas
from app.services import network_service
from app.deps import get_current_user, require_owner

router = APIRouter(prefix="/network", dependencies=[Depends(get_current_user)], tags=["network"])


def _listing_to_out(listing) -> schemas.NetworkListingOut:
    return schemas.NetworkListingOut(
        id=listing.id, pharmacy_node_id=listing.pharmacy_node_id,
        pharmacy_shop_name=listing.pharmacy_node.shop_name if listing.pharmacy_node else "Unknown",
        listing_type=listing.listing_type, medicine_name=listing.medicine_name,
        composition=listing.composition,
        quantity=float(listing.quantity) if listing.quantity is not None else None,
        expiry_date=listing.expiry_date, note=listing.note, status=listing.status,
        claimed_by_node_id=listing.claimed_by_node_id,
        claimed_by_shop_name=listing.claimed_by_node.shop_name if listing.claimed_by_node else None,
        created_at=listing.created_at,
    )


@router.get("/nodes", response_model=list[schemas.PharmacyNodeOut])
def list_nodes(db: Session = Depends(get_db)):
    network_service.get_or_create_self_node(db)  # ensures "this shop" always appears in the list
    db.commit()
    return network_service.list_nodes(db)


@router.post("/nodes", response_model=schemas.PharmacyNodeOut, dependencies=[Depends(require_owner)])
def add_node(payload: schemas.PharmacyNodeCreate, db: Session = Depends(get_db)):
    """
    Owner-only: register a nearby participating pharmacy. See
    network_service.py's module docstring for the honest scoping note -
    each row here stands in for a separately-deployed shop instance in a
    real multi-tenant rollout.
    """
    return network_service.add_node(db, payload.shop_name, payload.api_base_url, payload.contact_phone)


@router.get("/listings", response_model=list[schemas.NetworkListingOut])
def list_listings(
    listing_type: str = Query(None),
    status: str = Query("open"),
    db: Session = Depends(get_db),
):
    listings = network_service.list_listings(db, listing_type=listing_type, status=status)
    return [_listing_to_out(l) for l in listings]


@router.post("/listings", response_model=schemas.NetworkListingOut)
def create_listing(payload: schemas.NetworkListingCreate, db: Session = Depends(get_db)):
    self_node = network_service.get_or_create_self_node(db)
    db.commit()
    listing = network_service.create_manual_listing(
        db, self_node.id, payload.listing_type, payload.medicine_name,
        composition=payload.composition, quantity=payload.quantity,
        expiry_date=payload.expiry_date, note=payload.note,
    )
    return _listing_to_out(listing)


@router.post("/listings/publish-near-expiry", response_model=list[schemas.NetworkListingOut])
def publish_near_expiry(days: int = Query(60, ge=1, le=180), db: Session = Depends(get_db)):
    """Auto-publishes this shop's own near-expiry batches (Expiry Tracker) as network listings."""
    listings = network_service.publish_near_expiry_listings(db, days=days)
    return [_listing_to_out(l) for l in listings]


@router.post("/listings/{listing_id}/claim", response_model=schemas.NetworkListingOut)
def claim_listing(listing_id: int, payload: schemas.ClaimListingRequest, db: Session = Depends(get_db)):
    try:
        listing = network_service.claim_listing(db, listing_id, payload.claiming_node_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _listing_to_out(listing)


@router.post("/listings/{listing_id}/fulfill", response_model=schemas.NetworkListingOut)
def fulfill_listing(listing_id: int, db: Session = Depends(get_db)):
    try:
        listing = network_service.fulfill_listing(db, listing_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _listing_to_out(listing)


@router.delete("/listings/{listing_id}", response_model=schemas.NetworkListingOut)
def withdraw_listing(listing_id: int, db: Session = Depends(get_db)):
    try:
        listing = network_service.withdraw_listing(db, listing_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _listing_to_out(listing)