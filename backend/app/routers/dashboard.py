from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app import models

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    total_medicines = db.query(func.count(models.Medicine.id)).scalar()
    pending_bills = db.query(func.count(models.Bill.id)).filter(
        models.Bill.status == "pending_review"
    ).scalar()
    unmatched_items = db.query(func.count(models.BillItem.id)).filter(
        models.BillItem.match_status == "unmatched"
    ).scalar()
    recent_changes = (
        db.query(models.RateHistory)
        .order_by(models.RateHistory.changed_at.desc())
        .limit(10)
        .all()
    )
    return {
        "total_medicines": total_medicines,
        "pending_bills_awaiting_review": pending_bills,
        "unmatched_items_needing_manual_link": unmatched_items,
        "recent_rate_changes": [
            {
                "medicine_id": r.medicine_id,
                "old_net_rate": float(r.old_net_rate) if r.old_net_rate is not None else None,
                "new_net_rate": float(r.new_net_rate) if r.new_net_rate is not None else None,
                "changed_at": r.changed_at,
            }
            for r in recent_changes
        ],
    }
