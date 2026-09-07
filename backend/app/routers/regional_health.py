"""
Regional Health Sentinel — API endpoints.

Scopes:
  GET  /regional-health/participation   — any logged-in user
  PUT  /regional-health/participation   — owner only
  GET  /regional-health/alerts          — any logged-in user (health signals
                                          are not owner-restricted, same as
                                          /network-integrity/alerts)
  PATCH /regional-health/alerts/{id}/status — owner only
  POST /regional-health/scan-now        — owner only (imports task directly
                                          per CELERY TASK RULE in the feature spec)

Import pattern for get_current_user / require_owner: always from app.deps,
never from app.routers.auth or any other router file.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel

from app.database import get_db
from app.deps import get_current_user, require_owner
from app import models, schemas
from app.services import regional_health_service

router = APIRouter(prefix="/regional-health", tags=["regional-health"])


class AlertStatusUpdate(BaseModel):
    status: str


@router.get("/participation", response_model=schemas.RegionalParticipationOut)
def get_participation(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Returns the current tenant's regional surveillance participation status."""
    return regional_health_service.get_or_create_region_participation(
        db, tenant_id=current_user.tenant_id
    )


@router.put("/participation", response_model=schemas.RegionalParticipationOut)
def update_participation(
    payload: schemas.RegionalParticipationUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_owner),
):
    """
    Owner-only: set this tenant's region_code and opt-in flag for regional
    surveillance. Once opted in, the tenant's SurveillanceDailyCount rows
    will be included in the cross-tenant regional spike aggregation.
    """
    try:
        return regional_health_service.update_region_participation(
            db,
            tenant_id=current_user.tenant_id,
            region_code=payload.region_code,
            opt_in=payload.opt_in,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/alerts", response_model=List[schemas.RegionalHealthAlertOut])
def get_alerts(
    status: str = Query("open"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Returns regional health alerts for the current tenant's region.
    Any logged-in user of an opted-in tenant can view alerts (health signals
    are not owner-restricted — same scoping convention as network-integrity
    alerts; only financial reports are owner-only in this codebase).
    Returns empty list if the tenant is not opted in or has no region set.
    """
    return regional_health_service.get_alerts_for_tenant(
        db, tenant_id=current_user.tenant_id, status=status
    )


@router.patch("/alerts/{alert_id}/status")
def update_alert_status(
    alert_id: int,
    payload: AlertStatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_owner),
):
    """
    Owner-only: acknowledge or dismiss a regional health alert.
    The calling tenant's region must match the alert's region.
    """
    try:
        return regional_health_service.update_alert_status(
            db,
            alert_id=alert_id,
            tenant_id=current_user.tenant_id,
            new_status=payload.status,
        )
    except ValueError as e:
        msg = str(e)
        if msg == "Alert not found":
            raise HTTPException(404, msg)
        raise HTTPException(400, msg)


@router.post("/scan-now")
def trigger_scan_now(
    current_user: models.User = Depends(require_owner),
):
    """
    Owner-only: manually trigger a regional health spike scan as a Celery task.
    Imports the actual task function and calls .delay() directly (per the
    CELERY TASK RULE in the feature spec — never string-based send_task).
    """
    from app.services.tasks import scan_regional_health_spikes_task
    task = scan_regional_health_spikes_task.delay()
    return {"status": "queued", "task_id": task.id}
