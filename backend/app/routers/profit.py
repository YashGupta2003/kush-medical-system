from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.services import profit_analytics_service
from app.deps import require_owner

router = APIRouter(prefix="/profit", dependencies=[Depends(require_owner)], tags=["profit"])

@router.get("/margins", response_model=List[schemas.MarginsItem])
def get_margins(db: Session = Depends(get_db), current_user: models.User = Depends(require_owner)):
    """GET /profit/margins — full margin list for all priced medicines"""
    medicines = db.query(models.Medicine).filter(
        models.Medicine.tenant_id == current_user.tenant_id,
        models.Medicine.mrp.isnot(None),
        models.Medicine.net_rate.isnot(None),
        models.Medicine.mrp > 0
    ).all()
    
    results = []
    for med in medicines:
        margin_pct = profit_analytics_service._margin_pct(med.mrp, med.net_rate)
        if margin_pct is not None:
            if margin_pct > 20:
                status = "healthy"
            elif margin_pct >= 10:
                status = "thin"
            else:
                status = "critical"
                
            results.append({
                "medicine_id": med.id,
                "name": med.particulars,
                "margin_pct": margin_pct,
                "mrp": float(med.mrp),
                "net_rate": float(med.net_rate),
                "status": status
            })
            
    return results

@router.get("/compression", response_model=List[schemas.MarginCompressionItem])
def get_compression(
    days: int = Query(90, ge=1, le=365),
    severity: Optional[str] = Query(None, regex="^(mild|moderate|severe)$"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_owner)
):
    """GET /profit/compression — detect_margin_compression"""
    return profit_analytics_service.detect_margin_compression(db, current_user.tenant_id, days=days, severity_filter=severity)

@router.get("/substitutes/{medicine_id}", response_model=schemas.BestMarginSubstituteResult)
def get_substitutes(medicine_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(require_owner)):
    """GET /profit/substitutes/{medicine_id} — get_best_margin_substitutes"""
    return profit_analytics_service.get_best_margin_substitutes(db, current_user.tenant_id, medicine_id)

@router.get("/distributor-report", response_model=List[schemas.DistributorDealItem])
def get_distributor_report(db: Session = Depends(get_db), current_user: models.User = Depends(require_owner)):
    """GET /profit/distributor-report — get_distributor_negotiation_report"""
    return profit_analytics_service.get_distributor_negotiation_report(db, current_user.tenant_id)

