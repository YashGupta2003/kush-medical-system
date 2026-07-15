"""
Matches a medicine name as OCR read it off a bill (e.g. "AMLOKIND-AT TABS")
against the master rate list (e.g. "AMLOKIND AT TAB") using fuzzy string
matching, since spacing/abbreviations/hyphenation differ bill to bill.
"""
import re
from typing import Optional
from rapidfuzz import process, fuzz
from sqlalchemy.orm import Session

from app.models import Medicine
from app.config import settings


def normalize(name: str) -> str:
    """Uppercase, strip punctuation/extra spaces - used for both storage and matching."""
    name = name.upper()
    name = re.sub(r"[^A-Z0-9 ]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def find_best_match(db: Session, raw_name: str) -> tuple[Optional[Medicine], float]:
    """
    Returns (medicine_or_None, confidence_score_0_to_100).
    Confidence below settings.fuzzy_match_threshold means: don't auto-link,
    let the user pick manually on the review screen.
    """
    target = normalize(raw_name)
    if not target:
        return None, 0.0

    # Pull candidate names once; for a ~5k-row master list this is cheap.
    # (For a much larger list, pre-filter by first token / trigram index instead.)
    candidates = db.query(Medicine.id, Medicine.normalized_name).all()
    if not candidates:
        return None, 0.0

    choices = {row.id: row.normalized_name for row in candidates}

    result = process.extractOne(
        target,
        choices,
        scorer=fuzz.token_sort_ratio,
    )
    if result is None:
        return None, 0.0

    matched_name, score, medicine_id = result
    if score < settings.fuzzy_match_threshold:
        return None, score

    medicine = db.query(Medicine).get(medicine_id)
    return medicine, score
