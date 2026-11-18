"""
Matches a medicine name as OCR read it off a bill against the master rate
list. Two layers, checked in order:

  1. LEARNED MAPPINGS (user_mappings table) - if a human has EVER manually
     linked this exact raw name to a medicine before, use that instantly at
     100% confidence.

  2. WEIGHTED FUZZY MATCHING - scores every candidate using THREE factors:
       - Name similarity (60% weight)
       - Pack size agreement (25% weight)
       - Company/brand agreement (15% weight)
"""
import re
from typing import Optional
from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from app.models import Medicine, UserMapping
from app.config import settings

WEIGHT_NAME = 0.60
WEIGHT_PACK = 0.25
WEIGHT_COMPANY = 0.15
PACK_MISMATCH_PENALTY = 35.0


def normalize(name: str) -> str:
    name = name.upper()
    name = re.sub(r"[^A-Z0-9 ]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def extract_pack_size(text: str) -> Optional[int]:
    if not text:
        return None
    text = text.upper()

    multi = re.search(r"(\d+)\s*[\*X]\s*(\d+)", text)
    if multi:
        return int(multi.group(1)) * int(multi.group(2))

    single = re.search(r"(\d+)\s*'?\s*S\b", text)
    if single:
        return int(single.group(1))

    return None


def extract_company_hint(raw_text: str, known_companies: set[str]) -> Optional[str]:
    text_norm = normalize(raw_text)
    for company in known_companies:
        if company and normalize(company) in text_norm:
            return company
    return None


def _weighted_score(target_name: str, target_pack: Optional[int], target_company: Optional[str],
                     candidate_name: str, candidate_pack: Optional[int], candidate_company: Optional[str]) -> float:
    name_score = fuzz.token_sort_ratio(target_name, candidate_name)

    weight_name, weight_pack, weight_company = WEIGHT_NAME, WEIGHT_PACK, WEIGHT_COMPANY
    pack_component = None
    company_component = None

    if target_pack is not None and candidate_pack is not None:
        pack_component = 100.0 if target_pack == candidate_pack else 0.0
    else:
        weight_name += weight_pack
        weight_pack = 0.0

    if target_company and candidate_company:
        company_component = 100.0 if normalize(target_company) == normalize(candidate_company) else 0.0
    else:
        weight_name += weight_company
        weight_company = 0.0

    score = weight_name * name_score
    if pack_component is not None:
        score += weight_pack * pack_component
    if company_component is not None:
        score += weight_company * company_component

    if target_pack is not None and candidate_pack is not None and target_pack != candidate_pack:
        score = max(0.0, score - PACK_MISMATCH_PENALTY)

    return score


def _mapping_query(db: Session, raw_name: str, distributor_id: Optional[int], tenant_id: Optional[int]):
    q = db.query(UserMapping).filter(UserMapping.raw_name == raw_name)
    # Explicit predicate: learned mappings are per-shop, and a global Celery
    # session would otherwise match another tenant's learned mapping.
    if tenant_id is not None:
        q = q.filter(UserMapping.tenant_id == tenant_id)
    if distributor_id is not None:
        q = q.filter(UserMapping.distributor_id == distributor_id)
    else:
        q = q.filter(UserMapping.distributor_id.is_(None))
    return q


def find_learned_mapping(db: Session, raw_name: str, distributor_id: Optional[int],
                         tenant_id: Optional[int] = None) -> Optional[Medicine]:
    normalized = normalize(raw_name)
    if not normalized:
        return None
    if tenant_id is None:
        tenant_id = db.info.get("tenant_id")

    mapping = _mapping_query(db, normalized, distributor_id, tenant_id).first()
    if mapping:
        return db.get(Medicine, mapping.medicine_id)

    # Fall back to a distributor-independent mapping, still within the shop.
    if distributor_id is not None:
        general = _mapping_query(db, normalized, None, tenant_id).first()
        if general:
            return db.get(Medicine, general.medicine_id)

    return None


def save_learned_mapping(db: Session, raw_name: str, medicine_id: int, distributor_id: Optional[int],
                         tenant_id: Optional[int] = None) -> None:
    normalized = normalize(raw_name)
    if not normalized:
        return
    if tenant_id is None:
        tenant_id = db.info.get("tenant_id")
    if tenant_id is None:
        medicine = db.get(Medicine, medicine_id)
        tenant_id = medicine.tenant_id if medicine is not None else None

    existing = _mapping_query(db, normalized, distributor_id, tenant_id).first()
    if existing:
        existing.medicine_id = medicine_id
    else:
        db.add(UserMapping(
            tenant_id=tenant_id, raw_name=normalized,
            medicine_id=medicine_id, distributor_id=distributor_id,
        ))
    db.flush()


def find_best_match(
    db: Session,
    raw_name: str,
    distributor_id: Optional[int] = None,
    raw_context: Optional[str] = None,
    tenant_id: Optional[int] = None,
) -> tuple[Optional[Medicine], float, str]:
    target = normalize(raw_name)
    if not target:
        return None, 0.0, "unmatched"
    if tenant_id is None:
        tenant_id = db.info.get("tenant_id")

    learned = find_learned_mapping(db, raw_name, distributor_id, tenant_id=tenant_id)
    if learned:
        return learned, 100.0, "learned"

    candidates_query = db.query(Medicine.id, Medicine.normalized_name, Medicine.unit, Medicine.company)
    if tenant_id is not None:
        candidates_query = candidates_query.filter(Medicine.tenant_id == tenant_id)
    candidates = candidates_query.all()
    if not candidates:
        return None, 0.0, "unmatched"

    target_pack = extract_pack_size(raw_name)
    known_companies = {row.company for row in candidates if row.company}
    target_company = extract_company_hint(raw_context or raw_name, known_companies)

    best_medicine_id, best_score = None, -1.0
    for row in candidates:
        candidate_pack = extract_pack_size(row.unit or "")
        score = _weighted_score(
            target, target_pack, target_company,
            row.normalized_name, candidate_pack, row.company,
        )
        if score > best_score:
            best_score, best_medicine_id = score, row.id

    if best_medicine_id is None or best_score < settings.fuzzy_match_threshold:
        return None, max(best_score, 0.0), "unmatched"

    medicine = db.get(Medicine, best_medicine_id)
    return medicine, best_score, "auto"
