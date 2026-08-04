"""
Profit margin analytics - a NEW, small, focused service (Pillar 2 addition).
No existing function computed profit margin, so this is added as its own
module rather than bolted inline into copilot_service.py, matching this
codebase's one-module-per-concern convention (see cost_calculator.py,
matcher.py, etc. for the same pattern).
"""
from typing import Optional

from sqlalchemy.orm import Session

from app import models
from app.services import graph_service


def _margin_pct(mrp, net_rate) -> Optional[float]:
    if mrp is None or net_rate is None or mrp <= 0:
        return None
    return round(float((mrp - net_rate) / mrp) * 100, 2)


def get_profit_margin_analysis(db: Session, condition: Optional[str] = None) -> dict:
    """
    Average profit margin % ((MRP - net_rate) / MRP) across the whole shop's
    priced catalog, and optionally for medicines associated with a specific
    condition (via PharmaGraph's TREATS edges - e.g. condition="Bacterial
    Infection" as a proxy for "antibiotics") so the two can be compared.

    Medicines missing an MRP or net_rate are excluded rather than treated as
    zero margin - a missing price isn't a 0% margin, it's just unknown.
    """
    all_medicines = db.query(models.Medicine).filter(
        models.Medicine.mrp.isnot(None),
        models.Medicine.net_rate.isnot(None),
        models.Medicine.mrp > 0,
    ).all()

    shop_margins = [m for m in (_margin_pct(med.mrp, med.net_rate) for med in all_medicines) if m is not None]
    shop_avg = round(sum(shop_margins) / len(shop_margins), 2) if shop_margins else None

    result = {
        "shop_average_margin_pct": shop_avg,
        "shop_priced_medicine_count": len(shop_margins),
    }

    if condition:
        condition_medicines = graph_service.get_medicines_for_condition(db, condition, in_stock_only=False)
        matched_ids = {c["medicine_id"] for c in condition_medicines}
        matched = [m for m in all_medicines if m.id in matched_ids]
        cond_margins = [x for x in (_margin_pct(m.mrp, m.net_rate) for m in matched) if x is not None]

        result["condition"] = condition
        result["condition_average_margin_pct"] = round(sum(cond_margins) / len(cond_margins), 2) if cond_margins else None
        result["condition_priced_medicine_count"] = len(cond_margins)
        if shop_avg is not None and result["condition_average_margin_pct"] is not None:
            result["difference_vs_shop_average_pct"] = round(result["condition_average_margin_pct"] - shop_avg, 2)

    return result