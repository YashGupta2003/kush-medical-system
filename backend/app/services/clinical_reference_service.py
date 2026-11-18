"""Database-backed, globally shared clinical reference catalogs.

The checked-in JSON files remain the deployable baseline and test fallback.
At runtime, non-empty database tables are authoritative. Cache entries use
the shared Redis/in-memory cache and are invalidated by the owner CRUD API.
"""
import json
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from app import models
from app.core.cache import cache_response

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def normalize_salt(value: str) -> str:
    return " ".join((value or "").upper().split())


def normalize_interaction_pair(salt_a: str, salt_b: str) -> tuple[str, str]:
    first, second = sorted((normalize_salt(salt_a), normalize_salt(salt_b)))
    if not first or not second or first == second:
        raise ValueError("an interaction must contain two different non-empty salts")
    return first, second


def _load_baseline() -> dict[str, list[dict[str, Any]]]:
    with (DATA_DIR / "salt_conditions.json").open(encoding="utf-8") as handle:
        salt_data = json.load(handle)
    with (DATA_DIR / "drug_interactions.json").open(encoding="utf-8") as handle:
        interaction_data = json.load(handle)

    return {
        "salt_conditions": [
            {
                "salt_name": normalize_salt(mapping["salt"]),
                "conditions": list(mapping["conditions"]),
                "is_active": True,
            }
            for mapping in salt_data.get("mappings", [])
        ],
        "drug_interactions": [
            {
                "salt_a": normalize_interaction_pair(pair["salt_a"], pair["salt_b"])[0],
                "salt_b": normalize_interaction_pair(pair["salt_a"], pair["salt_b"])[1],
                "severity": str(pair["severity"]).strip().lower(),
                "note": str(pair["note"]).strip(),
                "is_active": True,
            }
            for pair in interaction_data.get("interactions", [])
        ],
    }


def get_clinical_reference_data(db: Optional[Session] = None) -> dict[str, list[dict[str, Any]]]:
    """Return active records from the database, falling back to bundled JSON.

    An omitted session is supported for isolated/unit callers. An empty table
    also falls back to its baseline catalog, which keeps older fixtures and
    unmigrated local test databases usable.
    """
    if db is None:
        return _load_baseline()
    return _get_database_reference_data(db)


@cache_response(ttl_seconds=300, key_prefix="clinical_reference")
def _get_database_reference_data(db: Session) -> dict[str, list[dict[str, Any]]]:
    baseline = _load_baseline()
    salt_rows = db.query(models.SaltCondition).order_by(models.SaltCondition.salt_name).all()
    interaction_rows = db.query(models.DrugInteraction).order_by(
        models.DrugInteraction.salt_a,
        models.DrugInteraction.salt_b,
    ).all()

    salt_conditions = (
        [
            {
                "salt_name": row.salt_name,
                "conditions": list(row.conditions or []),
                "is_active": row.is_active,
            }
            for row in salt_rows if row.is_active
        ]
        if salt_rows else baseline["salt_conditions"]
    )
    drug_interactions = (
        [
            {
                "salt_a": row.salt_a,
                "salt_b": row.salt_b,
                "severity": row.severity,
                "note": row.note,
                "is_active": row.is_active,
            }
            for row in interaction_rows if row.is_active
        ]
        if interaction_rows else baseline["drug_interactions"]
    )
    return {
        "salt_conditions": salt_conditions,
        "drug_interactions": drug_interactions,
    }


def seed_clinical_data(db: Session, *, reseed: bool = False) -> dict[str, int]:
    """Idempotently seed empty tables, or upsert baseline entries when asked.

    ``reseed=True`` updates baseline records in place without deleting custom
    rows or reactivating entries an administrator has deactivated.
    The caller owns the transaction and should invalidate caches after commit.
    """
    baseline = _load_baseline()
    counts = {"salt_conditions": 0, "drug_interactions": 0}

    salt_table_empty = db.query(models.SaltCondition).count() == 0
    if reseed or salt_table_empty:
        for item in baseline["salt_conditions"]:
            row = db.query(models.SaltCondition).filter_by(salt_name=item["salt_name"]).first()
            if row is None:
                db.add(models.SaltCondition(**item))
                counts["salt_conditions"] += 1
            elif row.conditions != item["conditions"]:
                row.conditions = list(item["conditions"])
                counts["salt_conditions"] += 1

    interaction_table_empty = db.query(models.DrugInteraction).count() == 0
    if reseed or interaction_table_empty:
        for item in baseline["drug_interactions"]:
            salt_a, salt_b = normalize_interaction_pair(item["salt_a"], item["salt_b"])
            row = db.query(models.DrugInteraction).filter_by(salt_a=salt_a, salt_b=salt_b).first()
            if row is None:
                db.add(models.DrugInteraction(**item))
                counts["drug_interactions"] += 1
            elif row.severity != item["severity"] or row.note != item["note"]:
                row.severity = item["severity"]
                row.note = item["note"]
                counts["drug_interactions"] += 1

    db.flush()
    return counts
