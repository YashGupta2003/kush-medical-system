"""
PharmaGraph - Pillar 1: a medicine knowledge graph implemented as typed edges
on top of the existing relational schema (see models.GraphEdge for the full
design rationale).

This module is the ONLY place that reads/writes graph_edges directly -
every other service/router that wants graph data goes through the
functions here, never queries GraphEdge itself. That keeps the "what counts
as a valid edge" logic in one place.

Edge lifecycle:
  - CONTAINS edges are cheap to keep live - synced every time a medicine's
    composition is saved (see composition_service.set_medicine_composition,
    which calls sync_contains_edges_for_medicine after writing MedicineSalt
    rows).
  - SUPPLIES edges are cheap to keep live - synced every time a bill is
    confirmed (see routers/bills.py's confirm_bill).
  - SUBSTITUTES edges are expensive (an O(catalog) scan per medicine) - kept
    fresh by the periodic/on-demand rebuild task instead of on every edit.
  - INTERACTS_WITH and TREATS edges come from curated seed data
    (app/data/drug_interactions.json, app/data/salt_conditions.json) and
    are (re)loaded by seed_interaction_edges / seed_condition_edges - safe
    to re-run, always replaces rather than duplicates.
"""
import json
from contextlib import nullcontext
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app import models
from app.database import GLOBAL_GRAPH_EDGE_TYPES, bypass_tenant_filter
from app.services import clinical_reference_service


# ---------------------------------------------------------------------------
# Generic edge primitives - every other function in this module is built on
# these two.
# ---------------------------------------------------------------------------
def add_edge(
    db: Session,
    source_type: str, source_id, edge_type: str, target_type: str, target_id,
    weight: Optional[float] = None, metadata: Optional[dict] = None,
    replace: bool = True, tenant_id: Optional[int] = None,
) -> models.GraphEdge:
    """
    Creates (or, if replace=True, first deletes any existing edge with the
    same source/type/target and recreates it) a single directed edge. This
    upsert-like behavior is what makes every sync_* function below safe to
    call repeatedly without accumulating duplicate/stale edges.

    `tenant_id` is MANDATORY for derived edges (CONTAINS/SUPPLIES/SUBSTITUTES):
    an edge with NULL tenant_id would be invisible to the shop that created
    it. Curated reference edges (INTERACTS_WITH/TREATS) are deliberately
    global and pass tenant_id=None.
    """
    source_id, target_id = str(source_id), str(target_id)

    if tenant_id is None and edge_type not in GLOBAL_GRAPH_EDGE_TYPES:
        # Fall back to the active session tenant. A NULL tenant is only
        # tolerated in fully unscoped sessions (legacy rows / backfill jobs),
        # where there is no tenant to stamp and no tenant that could read the
        # edge anyway.
        tenant_id = db.info.get("tenant_id")

    is_global = edge_type in GLOBAL_GRAPH_EDGE_TYPES
    # Curated global rows must stay NULL even when add_edge() is called from
    # a tenant-scoped request. before_flush would otherwise stamp them with
    # the active tenant and make them invisible to every other shop.
    isolation_scope = bypass_tenant_filter(db) if is_global else nullcontext()

    with isolation_scope:
        if replace:
            q = db.query(models.GraphEdge).filter_by(
                source_type=source_type, source_id=source_id, edge_type=edge_type,
                target_type=target_type, target_id=target_id,
            )
            if is_global:
                q = q.filter(models.GraphEdge.tenant_id.is_(None))
            else:
                q = q.filter(models.GraphEdge.tenant_id == tenant_id)
            q.delete(synchronize_session=False)

        edge = models.GraphEdge(
            tenant_id=None if is_global else tenant_id,
            source_type=source_type, source_id=source_id, edge_type=edge_type,
            target_type=target_type, target_id=target_id, weight=weight,
            edge_metadata=json.dumps(metadata) if metadata else None,
        )
        db.add(edge)
    return edge


def get_neighbors(
    db: Session, node_type: str, node_id, edge_type: Optional[str] = None, direction: str = "out",
) -> list[models.GraphEdge]:
    """
    direction="out": edges where this node is the SOURCE (e.g. this medicine CONTAINS these salts)
    direction="in":  edges where this node is the TARGET (e.g. these distributors SUPPLY this medicine)
    direction="both": either
    """
    node_id = str(node_id)
    out_filter = and_(models.GraphEdge.source_type == node_type, models.GraphEdge.source_id == node_id)
    in_filter = and_(models.GraphEdge.target_type == node_type, models.GraphEdge.target_id == node_id)

    q = db.query(models.GraphEdge)
    if direction == "out":
        q = q.filter(out_filter)
    elif direction == "in":
        q = q.filter(in_filter)
    else:
        from sqlalchemy import or_
        q = q.filter(or_(out_filter, in_filter))

    if edge_type:
        q = q.filter(models.GraphEdge.edge_type == edge_type)
    return q.all()


# ---------------------------------------------------------------------------
# CONTAINS: medicine -> salt (derived from MedicineSalt, kept live)
# ---------------------------------------------------------------------------
def sync_contains_edges_for_medicine(db: Session, medicine_id: int) -> None:
    medicine = db.get(models.Medicine, medicine_id)
    if medicine is None:
        return
    tenant_id = medicine.tenant_id

    db.query(models.GraphEdge).filter_by(
        source_type="medicine", source_id=str(medicine_id), edge_type="CONTAINS",
    ).filter(models.GraphEdge.tenant_id == tenant_id).delete(synchronize_session=False)

    salts = db.query(models.MedicineSalt).filter_by(medicine_id=medicine_id).all()
    for salt in salts:
        add_edge(
            db, "medicine", medicine_id, "CONTAINS", "salt", salt.salt_name,
            metadata={"strength": salt.strength} if salt.strength else None,
            replace=False, tenant_id=tenant_id,
        )


# ---------------------------------------------------------------------------
# SUPPLIES: distributor -> medicine (derived from confirmed bills, kept live)
# ---------------------------------------------------------------------------
def sync_supplies_edge(db: Session, distributor_id: Optional[int], medicine_id: int) -> None:
    if not distributor_id:
        return
    medicine = db.get(models.Medicine, medicine_id)
    if medicine is None:
        return
    add_edge(
        db, "distributor", distributor_id, "SUPPLIES", "medicine", medicine_id,
        tenant_id=medicine.tenant_id,
    )


# ---------------------------------------------------------------------------
# SUBSTITUTES: medicine -> medicine (expensive, rebuilt periodically)
# ---------------------------------------------------------------------------
def sync_substitute_edges_for_medicine(db: Session, medicine_id: int) -> int:
    """Returns the number of substitute edges written for this medicine."""
    from app.services import composition_service

    medicine = db.get(models.Medicine, medicine_id)
    if medicine is None:
        return 0

    db.query(models.GraphEdge).filter_by(
        source_type="medicine", source_id=str(medicine_id), edge_type="SUBSTITUTES",
    ).filter(models.GraphEdge.tenant_id == medicine.tenant_id).delete(synchronize_session=False)

    if not medicine.composition:
        return 0

    substitutes = composition_service.find_substitutes(
        db, medicine.composition, exclude_medicine_id=medicine_id, in_stock_only=False, limit=50,
    )
    for sub in substitutes:
        weight = round(100 * sub["matched_salts"] / sub["query_salts"], 2) if sub["query_salts"] else None
        add_edge(
            db, "medicine", medicine_id, "SUBSTITUTES", "medicine", sub["medicine_id"],
            weight=weight, metadata={"match_type": sub["match_type"]},
            replace=False, tenant_id=medicine.tenant_id,
        )
    return len(substitutes)


# ---------------------------------------------------------------------------
# INTERACTS_WITH: salt -> salt (curated seed data)
# ---------------------------------------------------------------------------
def seed_interaction_edges(db: Session, json_path: Optional[str] = None) -> int:
    """Replace the derived graph projection with database-first reference data."""
    if json_path:
        with open(json_path, encoding="utf-8") as f:
            interactions = json.load(f)["interactions"]
    else:
        interactions = clinical_reference_service.get_clinical_reference_data(db)["drug_interactions"]

    # Curated reference data is global: bypass the tenant guard explicitly so
    # the reload replaces the shared NULL-tenant rows, not a shop's own edges.
    with bypass_tenant_filter(db):
        db.query(models.GraphEdge).filter_by(edge_type="INTERACTS_WITH").filter(
            models.GraphEdge.tenant_id.is_(None)
        ).delete(synchronize_session=False)

    count = 0
    for pair in interactions:
        meta = {"severity": pair["severity"], "note": pair["note"]}
        # Stored both directions - interaction risk is symmetric (A interacts
        # with B is the same fact as B interacts with A), and callers only
        # ever need to look up "out" edges from whichever salt they have.
        add_edge(db, "salt", pair["salt_a"], "INTERACTS_WITH", "salt", pair["salt_b"], metadata=meta, replace=False)
        add_edge(db, "salt", pair["salt_b"], "INTERACTS_WITH", "salt", pair["salt_a"], metadata=meta, replace=False)
        count += 2
    return count


def check_interactions(db: Optional[Session], salt_names: list[str]) -> list[dict]:
    """
    Given a set of salts (e.g. every salt across the medicines in one sale
    or one bill), returns every known interacting pair found WITHIN that
    set. This is the function Pillar 3 (point-of-sale safety guardrail)
    calls.
    """
    salt_names = list({s.upper().strip() for s in salt_names if s and s.strip()})
    if len(salt_names) < 2:
        return []

    requested = set(salt_names)
    interactions = clinical_reference_service.get_clinical_reference_data(db)["drug_interactions"]
    return [
        {
            "salt_a": pair["salt_a"], "salt_b": pair["salt_b"],
            "severity": pair["severity"], "note": pair["note"],
        }
        for pair in interactions
        if pair["salt_a"] in requested and pair["salt_b"] in requested
    ]


# ---------------------------------------------------------------------------
# TREATS: salt -> condition (curated seed data)
# ---------------------------------------------------------------------------
def seed_condition_edges(db: Session, json_path: Optional[str] = None) -> int:
    if json_path:
        with open(json_path, encoding="utf-8") as f:
            mappings = json.load(f)["mappings"]
    else:
        mappings = clinical_reference_service.get_clinical_reference_data(db)["salt_conditions"]

    with bypass_tenant_filter(db):
        db.query(models.GraphEdge).filter_by(edge_type="TREATS").filter(
            models.GraphEdge.tenant_id.is_(None)
        ).delete(synchronize_session=False)

    count = 0
    for mapping in mappings:
        salt_name = mapping.get("salt_name", mapping.get("salt"))
        for condition in mapping["conditions"]:
            add_edge(db, "salt", salt_name, "TREATS", "condition", condition, replace=False)
            count += 1
    return count


def sync_reference_graph_edges(db: Session) -> dict[str, int]:
    """Refresh derived graph edges after baseline seed or admin edits."""
    return {
        "interactions": seed_interaction_edges(db),
        "treats": seed_condition_edges(db),
    }


def get_medicines_for_condition(db: Session, condition_name: str, in_stock_only: bool = True) -> list[dict]:
    """'What treats a Fever' - walks condition <- TREATS <- salt <- CONTAINS <- medicine."""
    condition_key = condition_name.strip().casefold()
    if not condition_key:
        return []
    reference = clinical_reference_service.get_clinical_reference_data(db)
    salt_names = [
        mapping["salt_name"]
        for mapping in reference["salt_conditions"]
        if any(condition.casefold() == condition_key for condition in mapping["conditions"])
    ]
    if not salt_names:
        return []

    contains_edges = (
        db.query(models.GraphEdge)
        .filter(
            models.GraphEdge.edge_type == "CONTAINS",
            models.GraphEdge.target_type == "salt",
            models.GraphEdge.target_id.in_(salt_names),
        )
        .all()
    )
    medicine_ids = list({int(e.source_id) for e in contains_edges})
    if not medicine_ids:
        return []

    q = db.query(models.Medicine).filter(models.Medicine.id.in_(medicine_ids))
    if in_stock_only:
        q = q.filter(models.Medicine.current_stock > 0)

    return [
        {
            "medicine_id": m.id, "particulars": m.particulars, "company": m.company,
            "composition": m.composition, "current_stock": float(m.current_stock or 0),
            "mrp": float(m.mrp) if m.mrp is not None else None,
        }
        for m in q.all()
    ]


# ---------------------------------------------------------------------------
# Full neighborhood view for one medicine - powers the Graph Explorer page.
# ---------------------------------------------------------------------------
def get_medicine_graph(db: Session, medicine_id: int) -> Optional[dict]:
    medicine = db.get(models.Medicine, medicine_id)
    if not medicine:
        return None

    contains_edges = get_neighbors(db, "medicine", medicine_id, edge_type="CONTAINS", direction="out")
    salt_names = [e.target_id for e in contains_edges]

    reference = clinical_reference_service.get_clinical_reference_data(db)
    medicine_salts = set(salt_names)
    interacts = []
    for pair in reference["drug_interactions"]:
        if pair["salt_a"] in medicine_salts:
            interacts.append({
                "salt": pair["salt_a"], "interacts_with": pair["salt_b"],
                "severity": pair["severity"], "note": pair["note"],
            })
        if pair["salt_b"] in medicine_salts:
            interacts.append({
                "salt": pair["salt_b"], "interacts_with": pair["salt_a"],
                "severity": pair["severity"], "note": pair["note"],
            })

    treats = [
        {"salt": mapping["salt_name"], "condition": condition}
        for mapping in reference["salt_conditions"]
        if mapping["salt_name"] in medicine_salts
        for condition in mapping["conditions"]
    ]

    substitute_edges = get_neighbors(db, "medicine", medicine_id, edge_type="SUBSTITUTES", direction="out")
    substitute_ids = [int(e.target_id) for e in substitute_edges]
    substitute_medicines = {
        m.id: m for m in db.query(models.Medicine).filter(models.Medicine.id.in_(substitute_ids)).all()
    } if substitute_ids else {}
    substitutes = []
    for e in substitute_edges:
        m = substitute_medicines.get(int(e.target_id))
        if m:
            substitutes.append({
                "medicine_id": m.id, "particulars": m.particulars, "company": m.company,
                "current_stock": float(m.current_stock or 0), "weight": float(e.weight) if e.weight is not None else None,
            })

    supplies_edges = get_neighbors(db, "medicine", medicine_id, edge_type="SUPPLIES", direction="in")
    distributor_ids = [int(e.source_id) for e in supplies_edges]
    distributors = db.query(models.Distributor).filter(models.Distributor.id.in_(distributor_ids)).all() if distributor_ids else []

    return {
        "medicine_id": medicine.id,
        "particulars": medicine.particulars,
        "composition": medicine.composition,
        "contains": [{"salt": s} for s in salt_names],
        "interacts_with": interacts,
        "treats": treats,
        "substitutes": sorted(substitutes, key=lambda s: -(s["weight"] or 0)),
        "supplied_by": [{"distributor_id": d.id, "name": d.name} for d in distributors],
    }


# ---------------------------------------------------------------------------
# Full rebuild - orchestrates every sync_* function above. Expensive
# (O(catalog) for the substitute edges especially) - meant to run as a
# Celery task (see services/tasks.py's rebuild_graph_task), not inline in
# a request.
# ---------------------------------------------------------------------------
def rebuild_full_graph(db: Session) -> dict:
    stats = {"contains": 0, "substitutes": 0, "supplies": 0, "interactions": 0, "treats": 0}

    medicines = db.query(models.Medicine).filter(models.Medicine.composition.isnot(None)).all()
    for med in medicines:
        sync_contains_edges_for_medicine(db, med.id)
        stats["contains"] += 1
    db.commit()

    for med in medicines:
        stats["substitutes"] += sync_substitute_edges_for_medicine(db, med.id)
    db.commit()

    confirmed_bills = db.query(models.Bill).filter(models.Bill.status == "confirmed").all()
    for bill in confirmed_bills:
        for item in bill.items:
            if item.medicine_id:
                sync_supplies_edge(db, bill.distributor_id, item.medicine_id)
                stats["supplies"] += 1
    db.commit()

    stats["interactions"] = seed_interaction_edges(db)
    stats["treats"] = seed_condition_edges(db)
    db.commit()

    return stats
