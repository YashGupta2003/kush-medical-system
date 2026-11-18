"""
Pillar 5, Part A.3 — Symptom-to-Stock-Check Bot (safe, RAG-grounded core logic).

SAFETY BOUNDARY (hard-coded, not configurable, not overridable by any
caller): this module NEVER outputs a diagnosis. It maps free-text symptom
mentions to condition CATEGORIES already curated in Pillar 1's PharmaGraph
(the exact same salt_conditions.json seed data that powers
/graph/condition/{name} - see graph_service.py), then checks THIS shop's
live stock for medicines associated with that category. Every response
ends with an explicit, hard-coded "confirm with the pharmacist" handoff
line.

This deliberately reuses Pillar 1's existing TREATS graph rather than
building a second, parallel symptom-matching system - the condition
vocabulary already seeded by graph_service.seed_condition_edges()
("Fever", "Pain", "Cough", "Allergy", "Acidity", ...) is exactly what this
matches against, so zero new curated data is required.

Production note (honest scoping, matching pharma_roadmap.md's own
framing): this module implements the SAFE MATCHING LOGIC only. The actual
WhatsApp transport (Twilio Business API - receiving an inbound webhook,
verifying its signature, sending the reply back out) is infrastructure,
not logic, and needs a real phone number + Twilio account to build and
test - it isn't wired up here. What IS wired up is a plain authenticated
REST endpoint (POST /symptom-bot/query, see routers/symptom_bot.py) that
calls answer_symptom_query() below, so the matching logic itself is fully
demoable and testable today. Swapping in a Twilio webhook that calls this
same function is a small, well-defined follow-up once those credentials
exist.
"""
import re
from typing import Optional

from sqlalchemy.orm import Session

from app.services import clinical_reference_service, graph_service

PHARMACIST_HANDOFF = (
    "This is a stock/category suggestion only, not a diagnosis or medical advice. "
    "Please confirm the right choice and correct dosage with the pharmacist before purchase."
)


def _known_conditions(db: Optional[Session] = None) -> list[str]:
    """Distinct active condition names from the shared clinical reference data."""
    reference = clinical_reference_service.get_clinical_reference_data(db)
    return sorted({
        condition
        for mapping in reference["salt_conditions"]
        for condition in mapping["conditions"]
    })


def match_symptoms_to_conditions(db: Optional[Session], message: str) -> list[str]:
    """
    Simple, deliberately conservative substring matching against the
    curated condition vocabulary - NOT free-form LLM inference over raw
    symptom text, precisely because an ungrounded model guessing at
    medical categories is the exact safety risk this module exists to
    avoid. A symptom that doesn't match any known condition returns no
    match at all (the caller reports "matched: false") rather than a
    guessed one.
    """
    text = message.upper()
    matched = []
    for condition in _known_conditions(db):
        words = [w for w in re.split(r"[,/\s]+", condition.upper()) if len(w) > 3]
        if condition.upper() in text or any(w in text for w in words):
            matched.append(condition)
    return matched


def answer_symptom_query(db: Session, message: str) -> dict:
    """
    Returns:
      {
        "matched": bool,
        "conditions": [str, ...],
        "suggestions": {condition: [ConditionMedicineItem-shaped dict, ...]},
        "reply": str,          # short, chat-ready summary
        "disclaimer": str,     # always present, always the same hard-coded text
      }
    """
    conditions = match_symptoms_to_conditions(db, message)

    if not conditions:
        return {
            "matched": False,
            "conditions": [],
            "suggestions": {},
            "reply": (
                "I couldn't confidently match that to a category I know about. "
                "Please describe the symptom more simply (e.g. 'fever', 'headache', "
                "'cough') or speak with the pharmacist directly."
            ),
            "disclaimer": PHARMACIST_HANDOFF,
        }

    suggestions = {}
    for condition in conditions:
        meds = graph_service.get_medicines_for_condition(db, condition, in_stock_only=True)
        suggestions[condition] = meds[:5]

    parts = []
    for condition, meds in suggestions.items():
        if meds:
            names = ", ".join(m["particulars"] for m in meds[:3])
            parts.append(f"For {condition.lower()}, in-stock options include: {names}.")
        else:
            parts.append(f"For {condition.lower()}, nothing matching is currently in stock — please check with the pharmacist for alternatives.")

    reply = " ".join(parts) + " " + PHARMACIST_HANDOFF

    return {
        "matched": True,
        "conditions": conditions,
        "suggestions": suggestions,
        "reply": reply,
        "disclaimer": PHARMACIST_HANDOFF,
    }
