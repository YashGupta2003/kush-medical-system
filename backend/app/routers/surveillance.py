from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.deps import require_owner
from app.services import surveillance_service, tasks
from app.schemas import SurveillanceConditionSummary, SurveillanceTrendPoint, SurveillanceSpikeAlert

router = APIRouter(
    prefix="/surveillance",
    tags=["Surveillance"],
    dependencies=[Depends(require_owner)]
)

@router.get("/conditions", response_model=List[SurveillanceConditionSummary])
def get_conditions(db: Session = Depends(get_db)):
    return surveillance_service.get_all_conditions_summary(db)

@router.get("/trend/{condition_name}", response_model=List[SurveillanceTrendPoint])
def get_trend(condition_name: str, days: int = Query(30), db: Session = Depends(get_db)):
    return surveillance_service.get_trend_data(db, condition_name, days)

@router.get("/spikes", response_model=List[SurveillanceSpikeAlert])
def get_spikes(days: int = Query(14), z_threshold: float = Query(2.0), db: Session = Depends(get_db)):
    return surveillance_service.detect_spikes(db, days, z_threshold)

@router.post("/scan-now")
def trigger_scan():
    task = tasks.run_surveillance_scan_task.delay()
    return {"message": "Scan started", "task_id": task.id}
