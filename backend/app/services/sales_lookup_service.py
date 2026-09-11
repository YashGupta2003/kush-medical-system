"""
Recent sales lookup - a NEW, small service (Pillar 2 addition). No existing
function exposed "what has been sold recently" directly (stock_service only
has per-medicine snapshots), so this is added standalone.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app import models


def get_recent_sales(db: Session, tenant_id: int, hours: int = 24) -> list[dict]:
    """Every Sale row in the last `hours` hours, most recent first."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    sales = (
        db.query(models.Sale)
        .filter(models.Sale.tenant_id == tenant_id, models.Sale.sold_at >= since)
        .order_by(models.Sale.sold_at.desc())
        .all()
    )

    results = []
    for sale in sales:
        medicine = db.get(models.Medicine, sale.medicine_id)
        results.append({
            "sale_id": sale.id,
            "medicine_id": sale.medicine_id,
            "medicine_name": medicine.particulars if medicine else "Unknown",
            "composition": medicine.composition if medicine else None,
            "qty_sold": float(sale.qty_sold),
            "sold_at": sale.sold_at.isoformat() if sale.sold_at else None,
        })
    return results