"""
Pillar 3 - Safety Guardrail Layer: point-of-sale drug-interaction checking.

Builds directly on Pillar 1's PharmaGraph (graph_service.check_interactions).
This is a distinct, synchronous, ALWAYS-ON safety check that runs at the
moment of sale, not something the Owner has to think to ask PharmaCopilot
about.

Design: a "cart" of {medicine_id, qty_sold} pairs is checked as a WHOLE
before anything is recorded. Two kinds of flags are checked, both
returned in the same `interactions` list so the frontend's warning
banner shows them together:

  1. Known INTERACTS_WITH pairs (curated seed data, e.g. Warfarin +
     Aspirin) - see graph_service.check_interactions().
  2. Duplicate active ingredients across DIFFERENT cart items (e.g.
     Combiflam Syp + Aceclowal SP both containing Paracetamol) - an
     overdose/double-dosing risk that (1) doesn't catch, since a salt
     doesn't "interact" with itself in the curated dataset. See
     _find_duplicate_salts() below.

If either kind of flag is present, recording is blocked with
status="needs_confirmation" - the pharmacist must explicitly acknowledge
(confirm_override=true) to proceed. This mirrors the same "warn first,
human confirms to override" pattern already used elsewhere in this app
(duplicate-invoice detection on the bills side) - never a silent block,
never a silent bypass, and the check runs server-side (not just as a UI
hint) so it can't be skipped by calling the API directly.

This intentionally does NOT touch the bill-confirmation OCR pipeline at
all - it only guards the "Record a Sale" flow (over-the-counter sales to
walk-in customers), which is where drug combinations are actually decided
in real time, unlike a purchase bill.

Pillar 5 integration: a cart sale can optionally be linked to a Customer
(customer_id) and recorded as "credit" (udhaar) instead of "cash" via
payment_mode. When it is, the total cart value (sum of each item's MRP *
qty) is charged to that customer's credit ledger via
customer_service.charge_credit() AFTER every item's stock has already
been successfully recorded.

Pillar 6 integration: created_by_user_id (the logged-in staff member
recording the sale, passed by routers/pos.py) is threaded through to
every stock_service.record_sale() call, so sales - like manual stock
adjustments - are attributable to a staff account for later analysis.

If any item fails, the whole request's exception propagates and the
caller's request-scoped session rolls back everything - a cart is never
half-recorded, and neither is its credit charge.
"""
from typing import Optional

from sqlalchemy.orm import Session

from app import models
from app.services import graph_service, stock_service, customer_service


def _medicine_salts(db: Session, medicine_id: int) -> list[str]:
    edges = graph_service.get_neighbors(db, "medicine", medicine_id, edge_type="CONTAINS", direction="out")
    return [e.target_id for e in edges]


def _find_duplicate_salts(item_details: list[dict]) -> list[dict]:
    """
    Flags a salt that appears in TWO OR MORE DIFFERENT medicines in the
    cart - e.g. Combiflam Syp + Aceclowal SP both containing Paracetamol.
    This is an overdose/duplication risk that curated INTERACTS_WITH pairs
    don't catch (a salt doesn't "interact" with itself in that dataset).
    """
    salt_to_medicines: dict[str, list[str]] = {}
    for item in item_details:
        for salt in item["salts"]:
            salt_to_medicines.setdefault(salt, []).append(item["particulars"])

    flags = []
    for salt, medicine_names in salt_to_medicines.items():
        unique_names = sorted(set(medicine_names))
        if len(unique_names) >= 2:
            flags.append({
                "salt_a": salt, "salt_b": salt, "severity": "medium",
                "note": f"'{salt}' appears in multiple cart items ({', '.join(unique_names)}) "
                        f"— check for unintentional double-dosing before selling together.",
            })
    return flags


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
    `interactions` combines curated INTERACTS_WITH pairs AND
    within-cart duplicate-salt flags (see _find_duplicate_salts) - the
    frontend doesn't need to know the difference, both are "flag this
    combination to the pharmacist before selling."
    """
    all_salts: set[str] = set()
    item_details = []

    for entry in items:
        medicine = db.get(models.Medicine, entry["medicine_id"])
        if not medicine:
            continue
        salts = _medicine_salts(db, medicine.id)
        all_salts.update(salts)
        item_details.append({
            "medicine_id": medicine.id, "particulars": medicine.particulars, "salts": salts,
        })

    interactions = graph_service.check_interactions(db, list(all_salts)) if len(all_salts) >= 2 else []
    interactions += _find_duplicate_salts(item_details)

    return {
        "has_interactions": len(interactions) > 0,
        "interactions": interactions,
        "items": item_details,
    }


def record_cart_sale(
    db: Session,
    items: list[dict],
    confirm_override: bool = False,
    customer_id: Optional[int] = None,
    payment_mode: str = "cash",
    created_by_user_id: Optional[int] = None,
) -> dict:
    """
    Checks the cart for interactions first (curated pairs + duplicate
    salts - see check_cart_interactions). If any are found and
    confirm_override is not True, records NOTHING and returns
    status="needs_confirmation" with the check details. Only once
    confirmed (or if there were never any flags) does it call
    stock_service.record_sale for every item in the cart.

    customer_id/payment_mode (Pillar 5) and created_by_user_id (Pillar 6)
    are all optional - a plain walk-in cash sale with none of them set
    works exactly as it always has.
    """
    check = check_cart_interactions(db, items)
    if check["has_interactions"] and not confirm_override:
        return {"status": "needs_confirmation", **check, "results": []}

    results = []
    total_value = 0.0
    for entry in items:
        snapshot = stock_service.record_sale(
            db, entry["medicine_id"], entry["qty_sold"],
            customer_id=customer_id, created_by_user_id=created_by_user_id,
        )
        results.append(snapshot)

        medicine = db.get(models.Medicine, entry["medicine_id"])
        if medicine and medicine.mrp is not None:
            total_value += float(medicine.mrp) * float(entry["qty_sold"])

    credit_result = None
    if payment_mode == "credit" and customer_id and total_value > 0:
        item_names = ", ".join(r["medicine_name"] for r in results)
        credit_result = customer_service.charge_credit(
            db, customer_id, total_value, note=f"Cart sale: {item_names}",
        )

    return {
        "status": "recorded", **check, "results": results,
        "total_value": round(total_value, 2),
        "payment_mode": payment_mode,
        "credit_balance_after": credit_result["resulting_balance"] if credit_result else None,
    }