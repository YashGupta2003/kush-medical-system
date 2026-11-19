"""
Recent sales lookup - a NEW, small service (Pillar 2 addition). No existing
function exposed "what has been sold recently" directly (stock_service only
has per-medicine snapshots), so this is added standalone.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app import models


def _f(value):
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


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
        medicine = db.get(models.Medicine, sale.medicine_id) if sale.medicine_id else None
        inv = getattr(sale, "invoice", None)
        results.append({
            "sale_id": sale.id,
            "sale_invoice_id": sale.sale_invoice_id or (inv.id if inv else None),
            "sale_invoice_number": inv.invoice_number if inv else None,
            "medicine_id": sale.medicine_id,
            "medicine_name": getattr(sale, "medicine_name_snapshot", None) or (medicine.particulars if medicine else "Unknown"),
            "composition": getattr(sale, "medicine_composition_snapshot", None) or (medicine.composition if medicine else None),
            "qty_sold": float(sale.qty_sold),
            "sold_at": sale.sold_at.isoformat() if sale.sold_at else None,
            # Issue 5: additive snapshot fields (prefer stored snapshots, fallback to None)
            "unit_mrp_snapshot": _f(getattr(sale, "unit_mrp_snapshot", None)),
            "unit_cost_snapshot": _f(getattr(sale, "unit_cost_snapshot", None)),
            "gst_pct_snapshot": _f(getattr(sale, "gst_pct_snapshot", None)),
            "line_subtotal": _f(getattr(sale, "line_subtotal", None)),
            "line_tax_amount": _f(getattr(sale, "line_tax_amount", None)),
            "line_total": _f(getattr(sale, "line_total", None)),
            "line_profit": _f(getattr(sale, "line_profit", None)),
        })
    return results