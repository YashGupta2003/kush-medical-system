from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Any, Optional
from app.database import get_db
from app.deps import get_current_user, require_owner
from app.schemas import (
    ColdChainUnitCreate,
    ColdChainUnitOut,
    ColdChainUnitUpdate,
    ColdChainReadingCreate,
    ColdChainReadingOut,
    ColdChainComplianceReport,
    ColdChainBatchOut
)
from app.services import cold_chain_service
from pydantic import BaseModel

router = APIRouter(prefix="/cold-chain", tags=["cold-chain"])

@router.post("/units", response_model=ColdChainUnitOut)
def create_unit(unit: ColdChainUnitCreate, db: Session = Depends(get_db), current_user = Depends(require_owner)):
    return cold_chain_service.create_unit(
        db=db,
        unit_label=unit.unit_label,
        location_note=unit.location_note,
        min_temp_c=unit.min_temp_c,
        max_temp_c=unit.max_temp_c
    )

@router.get("/units", response_model=List[ColdChainUnitOut])
def list_units(active_only: bool = True, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    return cold_chain_service.list_units(db=db, active_only=active_only)

@router.put("/units/{unit_id}", response_model=ColdChainUnitOut)
def update_unit(unit_id: int, unit: ColdChainUnitUpdate, db: Session = Depends(get_db), current_user = Depends(require_owner)):
    updated = cold_chain_service.update_unit(db=db, unit_id=unit_id, **unit.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Unit not found")
    return updated

@router.post("/readings", response_model=ColdChainReadingOut)
def record_reading(reading: ColdChainReadingCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    try:
        r = cold_chain_service.record_reading(
            db=db,
            unit_id=reading.unit_id,
            temp_c=reading.recorded_temp_c,
            recorded_by_user_id=current_user.id,
            note=reading.note
        )
        return {
            "id": r.id,
            "unit_id": r.unit_id,
            "unit_label": r.unit.unit_label,
            "recorded_temp_c": r.recorded_temp_c,
            "recorded_by_username": current_user.username,
            "recorded_at": r.recorded_at,
            "note": r.note,
            "is_excursion": r.is_excursion
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/readings/{unit_id}", response_model=List[ColdChainReadingOut])
def get_readings(unit_id: int, hours: int = 24, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    return cold_chain_service.get_readings(db=db, unit_id=unit_id, hours=hours)

@router.get("/compliance", response_model=ColdChainComplianceReport)
def get_compliance(days: int = 30, unit_id: Optional[int] = None, db: Session = Depends(get_db), current_user = Depends(require_owner)):
    return cold_chain_service.get_compliance_report(db=db, unit_id=unit_id, days=days)

@router.get("/compromised/{unit_id}", response_model=List[ColdChainBatchOut])
def get_compromised_batches(unit_id: int, db: Session = Depends(get_db), current_user = Depends(require_owner)):
    return cold_chain_service.get_compromised_batches(db=db, unit_id=unit_id)

class ToggleBatchColdChain(BaseModel):
    is_cold_chain: bool

@router.patch("/batches/{batch_id}/cold-chain", response_model=ColdChainBatchOut)
def toggle_batch_cold_chain(batch_id: int, payload: ToggleBatchColdChain, db: Session = Depends(get_db), current_user = Depends(require_owner)):
    batch = cold_chain_service.mark_batch_cold_chain(db=db, batch_id=batch_id, is_cold_chain=payload.is_cold_chain)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    return {
        "batch_id": batch.id,
        "medicine_id": batch.medicine_id,
        "medicine_name": batch.medicine.particulars,
        "batch_no": batch.batch_no,
        "expiry_date": batch.expiry_date,
        "qty_received": float(batch.qty_received),
        "is_cold_chain": batch.is_cold_chain
    }
