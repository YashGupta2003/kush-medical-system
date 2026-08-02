"""
PharmaGraph endpoints - read-only graph queries plus an owner-only rebuild
trigger. All the actual graph logic lives in services/graph_service.py;
this file only shapes requests/responses, matching this codebase's existing
router convention (see routers/bills.py, routers/stock.py for the same
pattern).
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas
from app.services import graph_service
from app.deps import get_current_user, require_owner

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
def trigger_rebuild():
    """
    Owner-only: kicks off a full graph rebuild (CONTAINS + SUBSTITUTES for
    every medicine, SUPPLIES for every confirmed bill, plus reloading the
    curated INTERACTS_WITH/TREATS seed data) as a background Celery task -
    see services/tasks.py's rebuild_graph_task for why this can't run
    inline in the request.
    """
    from app.services.tasks import rebuild_graph_task

    task = rebuild_graph_task.delay()
    return schemas.GraphRebuildResponse(task_id=task.id, status="queued")


@router.get("/rebuild/{task_id}/status", response_model=schemas.GraphRebuildStatus)
def rebuild_status(task_id: str):
    """Poll the status/result of a rebuild task started via POST /graph/rebuild."""
    from app.celery_app import celery_app

    result = celery_app.AsyncResult(task_id)
    if result.state == "PENDING":
        return schemas.GraphRebuildStatus(status="pending")
    if result.state == "SUCCESS":
        payload = result.result or {}
        return schemas.GraphRebuildStatus(status=payload.get("status", "ok"), stats=payload.get("stats"))
    if result.state == "FAILURE":
        return schemas.GraphRebuildStatus(status="failed", error=str(result.info))
    return schemas.GraphRebuildStatus(status=result.state.lower())
