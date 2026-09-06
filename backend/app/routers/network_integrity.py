from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from pydantic import BaseModel

from app.database import get_db
from app.routers.auth import get_current_user, require_owner
from app.services import cross_tenant_integrity_service
from app import models, schemas
from app.celery_app import celery_app

router = APIRouter(prefix="/network-integrity", tags=["network-integrity"])

class AlertStatusUpdate(BaseModel):
    status: str

@router.get("/alerts", response_model=List[schemas.CrossTenantAlertOut])
def get_alerts(
    status: str = Query("open"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Any logged-in user (Owner or Staff) of the affected tenant can view alerts.
    """
    return cross_tenant_integrity_service.get_alerts_for_tenant(
        db, tenant_id=current_user.tenant_id, status=status
    )

@router.patch("/alerts/{alert_id}/status")
def update_alert_status(
    alert_id: int,
    payload: AlertStatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_owner)
):
    """
    Only the Owner can dismiss/review an alert.
    """
    try:
        result = cross_tenant_integrity_service.update_alert_status(
            db, alert_id=alert_id, tenant_id=current_user.tenant_id, new_status=payload.status
        )
        return result
    except ValueError as e:
        msg = str(e)
        if msg == "Alert not found":
            raise HTTPException(404, msg)
        raise HTTPException(400, msg)

@router.post("/scan-now")
def trigger_scan_now(current_user: models.User = Depends(require_owner)):
    """
    Triggers scan_cross_tenant_batch_collisions_task.delay() manually.
    """
    task = celery_app.send_task("scan_cross_tenant_batch_collisions")
    return {"status": "queued", "task_id": task.id}
