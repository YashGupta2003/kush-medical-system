"""Owner-protected administration for the shared clinical reference catalogs."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.cache import invalidate_cache_prefix
from app.database import get_db
from app.deps import require_owner
from app.services.clinical_reference_service import seed_clinical_data
from app.services.graph_service import sync_reference_graph_edges


router = APIRouter(
    prefix="/clinical-reference",
    tags=["clinical reference"],
    dependencies=[Depends(require_owner)],
)


def _commit_reference_write(db: Session) -> None:
    try:
        db.flush()
        # GraphEdge is a read projection used by surveillance and graph views.
        # Refresh it in the same transaction as the clinical catalog write.
        invalidate_cache_prefix("clinical_reference")
        sync_reference_graph_edges(db)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        invalidate_cache_prefix("clinical_reference")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A clinical reference entry with the same normalized key already exists.",
        ) from exc
    except Exception:
        db.rollback()
        invalidate_cache_prefix("clinical_reference")
        raise
    invalidate_cache_prefix("clinical_reference")


@router.get("/salt-conditions", response_model=list[schemas.SaltConditionOut])
def list_salt_conditions(
    q: str | None = Query(None, description="Search salt names and mapped conditions"),
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    rows = db.query(models.SaltCondition).order_by(models.SaltCondition.salt_name).all()
    if not include_inactive:
        rows = [row for row in rows if row.is_active]
    if q and q.strip():
        needle = q.strip().casefold()
        rows = [
            row for row in rows
            if needle in row.salt_name.casefold()
            or any(needle in condition.casefold() for condition in (row.conditions or []))
        ]
    return rows


@router.post("/salt-conditions", response_model=schemas.SaltConditionOut, status_code=201)
def create_salt_condition(payload: schemas.SaltConditionCreate, db: Session = Depends(get_db)):
    row = models.SaltCondition(**payload.model_dump())
    db.add(row)
    _commit_reference_write(db)
    db.refresh(row)
    return row


@router.put("/salt-conditions/{record_id}", response_model=schemas.SaltConditionOut)
def update_salt_condition(
    record_id: int,
    payload: schemas.SaltConditionUpdate,
    db: Session = Depends(get_db),
):
    row = db.get(models.SaltCondition, record_id)
    if row is None:
        raise HTTPException(404, "Salt-condition entry not found")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(422, "Provide at least one field to update")
    for field, value in changes.items():
        setattr(row, field, value)
    _commit_reference_write(db)
    db.refresh(row)
    return row


@router.delete("/salt-conditions/{record_id}", response_model=schemas.SaltConditionOut)
def delete_salt_condition(record_id: int, db: Session = Depends(get_db)):
    row = db.get(models.SaltCondition, record_id)
    if row is None:
        raise HTTPException(404, "Salt-condition entry not found")
    row.is_active = False
    _commit_reference_write(db)
    db.refresh(row)
    return row


@router.get("/drug-interactions", response_model=list[schemas.DrugInteractionOut])
def list_drug_interactions(
    q: str | None = Query(None, description="Search either interacting salt or the note"),
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    rows = db.query(models.DrugInteraction).order_by(
        models.DrugInteraction.salt_a,
        models.DrugInteraction.salt_b,
    ).all()
    if not include_inactive:
        rows = [row for row in rows if row.is_active]
    if q and q.strip():
        needle = q.strip().casefold()
        rows = [
            row for row in rows
            if needle in row.salt_a.casefold()
            or needle in row.salt_b.casefold()
            or needle in row.note.casefold()
        ]
    return rows


@router.post("/drug-interactions", response_model=schemas.DrugInteractionOut, status_code=201)
def create_drug_interaction(payload: schemas.DrugInteractionCreate, db: Session = Depends(get_db)):
    row = models.DrugInteraction(**payload.model_dump())
    db.add(row)
    _commit_reference_write(db)
    db.refresh(row)
    return row


@router.put("/drug-interactions/{record_id}", response_model=schemas.DrugInteractionOut)
def update_drug_interaction(
    record_id: int,
    payload: schemas.DrugInteractionUpdate,
    db: Session = Depends(get_db),
):
    row = db.get(models.DrugInteraction, record_id)
    if row is None:
        raise HTTPException(404, "Drug-interaction entry not found")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(422, "Provide at least one field to update")
    for field, value in changes.items():
        setattr(row, field, value)
    _commit_reference_write(db)
    db.refresh(row)
    return row


@router.delete("/drug-interactions/{record_id}", response_model=schemas.DrugInteractionOut)
def delete_drug_interaction(record_id: int, db: Session = Depends(get_db)):
    row = db.get(models.DrugInteraction, record_id)
    if row is None:
        raise HTTPException(404, "Drug-interaction entry not found")
    row.is_active = False
    _commit_reference_write(db)
    db.refresh(row)
    return row


@router.post("/reseed-clinical-data")
def reseed_clinical_data(db: Session = Depends(get_db)):
    """Upsert baseline JSON entries while preserving custom and inactive rows."""
    counts = seed_clinical_data(db, reseed=True)
    invalidate_cache_prefix("clinical_reference")
    try:
        graph_stats = sync_reference_graph_edges(db)
        db.commit()
    except Exception:
        db.rollback()
        invalidate_cache_prefix("clinical_reference")
        raise
    invalidate_cache_prefix("clinical_reference")
    return {**counts, **graph_stats, "status": "ok"}
