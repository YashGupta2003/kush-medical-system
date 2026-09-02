from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.deps import get_current_user

router = APIRouter(prefix="/dashboard" , dependencies=[Depends(get_current_user)], tags=["dashboard"])


@router.get("/summary")
def summary(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    total_medicines = db.query(func.count(models.Medicine.id)).filter(
        models.Medicine.tenant_id == current_user.tenant_id
    ).scalar()

    raw_status_counts = (
        db.query(models.Bill.status, func.count(models.Bill.id))
        .filter(models.Bill.tenant_id == current_user.tenant_id)
        .group_by(models.Bill.status)
        .all()
    )
    status_counts = {}
    for st, cnt in raw_status_counts:
        key = st.value if hasattr(st, "value") else str(st) if st else "queued"
        status_counts[key] = cnt

    recent_changes = (
        db.query(models.RateHistory)
        .join(models.Medicine, models.RateHistory.medicine_id == models.Medicine.id)
        .filter(models.Medicine.tenant_id == current_user.tenant_id)
        .order_by(models.RateHistory.changed_at.desc())
        .limit(10)
        .all()
    )

    return {
        "total_medicines": total_medicines,
        "bill_status_counts": {
            "queued": status_counts.get("queued", 0),
            "processing": status_counts.get("processing", 0),
            "pending_review": status_counts.get("pending_review", 0),
            "needs_attention": status_counts.get("needs_attention", 0),
            "confirmed": status_counts.get("confirmed", 0),
            "failed": status_counts.get("failed", 0),
        },
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

