"""
Kush Pulse — Privacy-Preserving Regional Health Heatmap endpoints.

The GET endpoints are intentionally public: they expose only k-anonymous
aggregate signals (k >= 3), never shop, customer, bill, medicine or sale
identifiers. They are rate-limited to discourage enumeration.

The refresh endpoint is owner-only and synchronous so a shop owner can prove
the privacy rule in a live demo. Production refreshes normally come from the
Celery beat task.
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.rate_limit import limiter
from app.database import get_db
from app.deps import require_owner
from app.services import heatmap_service

router = APIRouter(prefix="/heatmap", tags=["heatmap"])


@router.get("/regional", response_model=Dict[str, Any])
@limiter.limit("60/minute")
def get_regional_heatmap(
    request: Request,
    condition_name: Optional[str] = None,
    region_code: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Latest privacy-safe heatmap. Safe to display publicly."""
    return heatmap_service.get_heatmap(
        db, condition_name=condition_name, region_code=region_code
    )


@router.get("/regions/{region_code}", response_model=Dict[str, Any])
@limiter.limit("60/minute")
def get_region_heatmap(
    region_code: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """One region's sanitized cells with a seven-day signal-label trend."""
    return heatmap_service.get_region_heatmap(db, region_code)


@router.post("/refresh", response_model=Dict[str, Any])
def refresh_heatmap(
    db: Session = Depends(get_db),
    current_user=Depends(require_owner),
):
    """Owner-only manual recompute — mainly used for demos and verification."""
    return heatmap_service.refresh_heatmap(db)
