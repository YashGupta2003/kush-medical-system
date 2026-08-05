"""
Pillar 3 - Safety Guardrail Layer: point-of-sale drug-interaction checking.

Builds directly on Pillar 1's PharmaGraph (graph_service.check_interactions).
This is a distinct, synchronous, ALWAYS-ON safety check that runs at the
moment of sale, not something the Owner has to think to ask PharmaCopilot
about.

Design: a "cart" of {medicine_id, qty_sold} pairs is checked as a WHOLE
before anything is recorded. If any two salts across the cart interact,
recording is blocked with status="needs_confirmation" describing exactly
what was flagged - the pharmacist must explicitly acknowledge
(confirm_override=true) to proceed. This mirrors the same "warn first,
human confirms to override" pattern already used elsewhere in this app
(duplicate-invoice detection on the bills side) - never a silent block,
never a silent bypass, and the check runs server-side (not just as a UI
hint) so it can't be skipped by calling the API directly.

This intentionally does NOT touch the bill-confirmation OCR pipeline at
all - it only guards the "Record a Sale" flow (over-the-counter sales to
walk-in customers), which is where drug combinations are actually decided
in real time, unlike a purchase bill.
"""
from sqlalchemy.orm import Session

from app import models
from app.services import graph_service, stock_service


def _medicine_salts(db: Session, medicine_id: int) -> list[str]:
    edges = graph_service.get_neighbors(db, "medicine", medicine_id, edge_type="CONTAINS", direction="out")
    return [e.target_id for e in edges]


def check_cart_interactions(db: Session, items: list[dict]) -> dict:
    """
    items: [{"medicine_id": int, "qty_sold": float}, ...] - qty_sold is
    accepted but unused here (this function only cares about WHICH
    medicines are in the cart, not how much of each).

    Returns:
      {
        "has_interactions": bool,
        "interactions": [{"salt_a", "salt_b", "severity", "note"}, ...],
        "items": [{"medicine_id", "particulars", "salts": [...]}, ...],
      }
    """
    all_salts: set[str] = set()
    item_details = []

    for entry in items:
        medicine = db.query(models.Medicine).get(entry["medicine_id"])
        if not medicine:
            continue
        salts = _medicine_salts(db, medicine.id)
        all_salts.update(salts)
        item_details.append({
            "medicine_id": medicine.id, "particulars": medicine.particulars, "salts": salts,
        })

    interactions = graph_service.check_interactions(db, list(all_salts)) if len(all_salts) >= 2 else []

    return {
        "has_interactions": len(interactions) > 0,
        "interactions": interactions,
        "items": item_details,
    }


def record_cart_sale(db: Session, items: list[dict], confirm_override: bool = False) -> dict:
    """
    Checks the cart for interactions first. If interactions are found and
    confirm_override is not True, records NOTHING and returns
    status="needs_confirmation" with the check details, so the caller can
    surface a warning and ask the pharmacist to explicitly confirm before
    retrying with confirm_override=True. Only once confirmed (or if there
    were never any interactions) does it call stock_service.record_sale
    for every item in the cart.

    If any individual item fails partway through (e.g. a medicine_id that
    no longer exists), the exception propagates and the caller's request
    fails as a whole - the FastAPI request-scoped session then rolls back,
    so a cart is never left half-recorded.
    """
    check = check_cart_interactions(db, items)
    if check["has_interactions"] and not confirm_override:
        return {"status": "needs_confirmation", **check, "results": []}

    results = []
    for entry in items:
        snapshot = stock_service.record_sale(db, entry["medicine_id"], entry["qty_sold"])
        results.append(snapshot)

    return {"status": "recorded", **check, "results": results}

def _find_duplicate_salts(item_details: list[dict]) -> list[dict]:
    """
    Flags a salt that appears in TWO OR MORE DIFFERENT medicines in the
    cart — e.g. Combiflam Syp + Aceclowal SP both containing Paracetamol.
    This is an overdose/duplication risk that curated INTERACTS_WITH pairs
    don't catch (a salt doesn't "interact" with itself in that dataset).
    """
    salt_to_medicines: dict[str, list[str]] = {}
    for item in item_details:
        for salt in item["salts"]:
            salt_to_medicines.setdefault(salt, []).append(item["particulars"])

    flags = []
    for salt, medicine_names in salt_to_medicines.items():
        if len(set(medicine_names)) >= 2:
            flags.append({
                "salt_a": salt, "salt_b": salt, "severity": "medium",
                "note": f"'{salt}' appears in multiple cart items ({', '.join(sorted(set(medicine_names)))}) "
                        f"— check for unintentional double-dosing before selling together.",
            })
    return flags


def check_cart_interactions(db: Session, items: list[dict]) -> dict:
    all_salts: set[str] = set()
    item_details = []

    for entry in items:
        medicine = db.query(models.Medicine).get(entry["medicine_id"])
        if not medicine:
            continue
        salts = _medicine_salts(db, medicine.id)
        all_salts.update(salts)
        item_details.append({
            "medicine_id": medicine.id, "particulars": medicine.particulars, "salts": salts,
        })

    interactions = graph_service.check_interactions(db, list(all_salts)) if len(all_salts) >= 2 else []
    interactions += _find_duplicate_salts(item_details)   # 👈 add this line

    return {
        "has_interactions": len(interactions) > 0,
        "interactions": interactions,
        "items": item_details,
    }