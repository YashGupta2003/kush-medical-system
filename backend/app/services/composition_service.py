"""
Substitute Medicine Suggestion feature.

Real-world problem this solves: a prescription says "Crocin 650" but the shop
is out of Crocin. Dolo 650 has the exact same salt (Paracetamol 650mg) from a
different company and works identically - but nothing in the old rate-list
Excel sheet ever captured that connection, so the shopkeeper had to know it
from memory.

Design: rather than fuzzy-matching whole composition STRINGS (brittle -
"Paracetamol 650mg" vs "Paracetamol 650 mg" vs "Paracetamol IP 650mg" would
all look different), every medicine's composition is parsed into individual
(salt_name, strength) rows in medicine_salts. Substitute search then matches
on the parsed salt set, which is what actually determines clinical
equivalence - not surface text.

This is deliberately NOT a drug-interaction or dosage-safety engine - it only
tells the shopkeeper "these medicines share the same salt(s)", the same way
a pharmacist's own knowledge would. Final judgment always stays with the
shopkeeper/pharmacist.
"""
import re
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from app import models

# Splits "Paracetamol 650mg + Caffeine 30mg" / "... , ..." / "... and ..." into parts.
_SEPARATOR_RE = re.compile(r"\s*(?:\+|,|&|\bAND\b|\bWITH\b)\s*", re.IGNORECASE)

# Trailing strength token: a number followed by a unit (MG, MCG, ML, GM, G, IU, %).
_STRENGTH_RE = re.compile(
    r"(?P<strength>\d+(?:\.\d+)?\s*(?:MG|MCG|ML|GM|G|IU|%))\s*$", re.IGNORECASE
)


@dataclass
class ParsedSalt:
    salt_name: str      # normalized: uppercase, trimmed, collapsed whitespace
    strength: Optional[str]   # normalized uppercase, e.g. "650MG", or None if not found


def parse_composition(raw_text: Optional[str]) -> list[ParsedSalt]:
    """
    "Paracetamol 650mg + Caffeine 30mg"
      -> [ParsedSalt("PARACETAMOL", "650MG"), ParsedSalt("CAFFEINE", "30MG")]

    Defensive: unparseable or empty input returns an empty list rather than
    raising - a medicine with no composition data yet is a normal state
    (most of the master list starts this way), not an error.
    """
    if not raw_text or not raw_text.strip():
        return []

    parts = _SEPARATOR_RE.split(raw_text.strip())
    results = []
    for part in parts:
        part = part.strip()
        if not part:
            continue

        strength = None
        match = _STRENGTH_RE.search(part)
        name_part = part
        if match:
            strength = re.sub(r"\s+", "", match.group("strength")).upper()
            name_part = part[: match.start()].strip()

        salt_name = re.sub(r"\s+", " ", name_part).strip().upper()
        salt_name = salt_name.rstrip(".,-")
        if salt_name:
            results.append(ParsedSalt(salt_name=salt_name, strength=strength))

    return results


def set_medicine_composition(db: Session, medicine_id: int, raw_composition: str) -> Optional[models.Medicine]:
    """
    Parses raw_composition and (re)writes both medicine.composition (the raw
    display text) and the medicine's medicine_salts rows. Fully idempotent -
    safe to call repeatedly (e.g. re-running the bulk backfill script), since
    old salt rows are deleted before the new ones are inserted rather than
    appended.
    """
    medicine = db.query(models.Medicine).get(medicine_id)
    if not medicine:
        return None

    medicine.composition = raw_composition.strip() if raw_composition else None

    db.query(models.MedicineSalt).filter_by(medicine_id=medicine_id).delete()
    for parsed in parse_composition(raw_composition):
        db.add(models.MedicineSalt(
            medicine_id=medicine_id, salt_name=parsed.salt_name, strength=parsed.strength,
        ))

    return medicine


def _salts_query(db: Session, salt_names: list[str], exclude_medicine_id: Optional[int], in_stock_only: bool):
    q = (
        db.query(models.MedicineSalt.medicine_id, func.count(models.MedicineSalt.id.distinct()))
        .join(models.Medicine, models.Medicine.id == models.MedicineSalt.medicine_id)
        .filter(models.MedicineSalt.salt_name.in_(salt_names))
    )
    if exclude_medicine_id is not None:
        q = q.filter(models.MedicineSalt.medicine_id != exclude_medicine_id)
    if in_stock_only:
        q = q.filter(models.Medicine.current_stock > 0)
    return q.group_by(models.MedicineSalt.medicine_id)


def find_substitutes(
    db: Session,
    composition_or_salt_text: str,
    exclude_medicine_id: Optional[int] = None,
    in_stock_only: bool = True,
    limit: int = 25,
) -> list[dict]:
    """
    Parses the query text the same way medicine compositions are parsed, then
    finds every Medicine that shares at least one salt. Ranks results:
      - "exact"   : matches every salt in the query (order-independent) -
                    these are true like-for-like substitutes
      - "partial" : shares some but not all of the query's salts

    Filters to current_stock > 0 by default - the entire point is "what can
    this shop actually sell right now", not a general drug-composition
    lookup.
    """
    query_salts = parse_composition(composition_or_salt_text)
    if not query_salts:
        return []

    query_salt_names = [s.salt_name for s in query_salts]
    query_count = len(set(query_salt_names))

    matches = _salts_query(db, query_salt_names, exclude_medicine_id, in_stock_only).all()
    if not matches:
        return []

    medicine_ids = [m[0] for m in matches]
    overlap_by_id = {m[0]: m[1] for m in matches}

    medicines = (
        db.query(models.Medicine)
        .filter(models.Medicine.id.in_(medicine_ids))
        .all()
    )

    results = []
    for med in medicines:
        overlap = overlap_by_id.get(med.id, 0)
        match_type = "exact" if overlap >= query_count else "partial"
        results.append({
            "medicine_id": med.id,
            "particulars": med.particulars,
            "company": med.company,
            "unit": med.unit,
            "mrp": float(med.mrp) if med.mrp is not None else None,
            "current_stock": float(med.current_stock or 0),
            "composition": med.composition,
            "match_type": match_type,
            "matched_salts": overlap,
            "query_salts": query_count,
        })

    # Exact matches first, then partial - within each group, more overlap first,
    # then higher stock first (prefer suggesting something well-stocked).
    results.sort(key=lambda r: (r["match_type"] != "exact", -r["matched_salts"], -r["current_stock"]))
    return results[:limit]


def get_medicine_substitutes(db: Session, medicine_id: int, in_stock_only: bool = True, limit: int = 25) -> dict:
    """
    Convenience wrapper for "this exact medicine is out of stock, what else
    works" - looks up the medicine's own composition (works even if THIS
    medicine has zero stock) and searches from there, excluding itself.
    """
    medicine = db.query(models.Medicine).get(medicine_id)
    if not medicine:
        return {"medicine": None, "substitutes": []}

    if not medicine.composition:
        return {
            "medicine": {"id": medicine.id, "particulars": medicine.particulars, "composition": None},
            "substitutes": [],
        }

    substitutes = find_substitutes(
        db, medicine.composition, exclude_medicine_id=medicine.id,
        in_stock_only=in_stock_only, limit=limit,
    )
    return {
        "medicine": {"id": medicine.id, "particulars": medicine.particulars, "composition": medicine.composition},
        "substitutes": substitutes,
    }
