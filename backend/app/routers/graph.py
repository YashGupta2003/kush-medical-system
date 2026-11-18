"""
PharmaGraph endpoints - read-only graph queries plus an owner-only rebuild
trigger. All the actual graph logic lives in services/graph_service.py;
this file only shapes requests/responses, matching this codebase's existing
router convention (see routers/bills.py, routers/stock.py for the same
pattern).
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas
from app.services import graph_service
from app.deps import get_current_user, require_owner
from app.core.task_dispatch import dispatch_task, get_task_status

router = APIRouter(prefix="/graph", dependencies=[Depends(get_current_user)], tags=["graph"])


@router.get("/medicine/{medicine_id}", response_model=schemas.MedicineGraph)
def medicine_graph(medicine_id: int, db: Session = Depends(get_db)):
    """
    Full relationship neighborhood for one medicine - what it contains,
    what those salts interact with, what conditions they treat, what other
    medicines can substitute for it, and which distributors have supplied
    it. Powers the Graph Explorer screen.
    """
    result = graph_service.get_medicine_graph(db, medicine_id)
    if result is None:
        raise HTTPException(404, "Medicine not found")
    return result


@router.get("/check-interactions", response_model=list[schemas.InteractionCheckResult])
def check_interactions(
    salts: str = Query(..., description="Comma-separated salt names to check against each other"),
    db: Session = Depends(get_db),
):
    """
    Given a set of salts (e.g. every salt across the medicines in one sale),
    returns any known interacting pairs among them. This is the function
    Pillar 3's point-of-sale safety guardrail will call.
    """
    salt_list = [s.strip() for s in salts.split(",") if s.strip()]
    return graph_service.check_interactions(db, salt_list)


@router.get("/condition/{condition_name}", response_model=list[schemas.ConditionMedicineItem])
def medicines_for_condition(
    condition_name: str,
    in_stock_only: bool = True,
    db: Session = Depends(get_db),
):
    """'What do we have in stock that treats a Fever' - walks condition -> salt -> medicine."""
    return graph_service.get_medicines_for_condition(db, condition_name, in_stock_only=in_stock_only)


@router.post("/rebuild", response_model=schemas.GraphRebuildResponse, dependencies=[Depends(require_owner)])
def trigger_rebuild(background_tasks: BackgroundTasks):
    """
    Owner-only: kicks off a full graph rebuild through the shared dispatcher.

    Broker mode enqueues to Celery; eager/fallback mode runs it inline via
    FastAPI BackgroundTasks so the request never depends on Redis availability.
    """
    from app.services.tasks import rebuild_graph_task

    dispatch = dispatch_task(
        rebuild_graph_task, background_tasks=background_tasks
    )
    status = "queued"
    if dispatch.executed and dispatch.result:
        status = dispatch.result.get("status", "ok")
    return schemas.GraphRebuildResponse(task_id=dispatch.task_id, status=status)


@router.get("/rebuild/{task_id}/status", response_model=schemas.GraphRebuildStatus)
def rebuild_status(task_id: str):
    """Poll the status/result of a rebuild task started via POST /graph/rebuild."""
    payload = get_task_status(task_id)
    return schemas.GraphRebuildStatus(
        status=payload.get("status", "pending"),
        stats=payload.get("stats"),
        error=payload.get("error"),
    )
