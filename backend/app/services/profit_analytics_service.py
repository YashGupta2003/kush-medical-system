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

from datetime import datetime, timedelta, timezone

def detect_margin_compression(db: Session, days: int = 90, severity_filter: Optional[str] = None) -> list[dict]:
    # For each medicine: check last 2 RateHistory entries within days.
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    medicines = db.query(models.Medicine).all()
    results = []
    
    for med in medicines:
        history = db.query(models.RateHistory).filter(
            models.RateHistory.medicine_id == med.id,
            models.RateHistory.changed_at >= cutoff_date
        ).order_by(models.RateHistory.changed_at.desc()).limit(2).all()
        
        if len(history) < 2:
            # Check if there is at least one history entry where old and new are different
            # But the prompt says "For each medicine: check last 2 RateHistory entries."
            # Actually, a single RateHistory entry contains old_net_rate and new_net_rate, so one entry is enough if we look at the row itself!
            latest_history = db.query(models.RateHistory).filter(
                models.RateHistory.medicine_id == med.id,
                models.RateHistory.changed_at >= cutoff_date
            ).order_by(models.RateHistory.changed_at.desc()).first()
            
            if not latest_history:
                continue
        else:
            latest_history = history[0]
            
        old_net = float(latest_history.old_net_rate) if latest_history.old_net_rate else None
        new_net = float(latest_history.new_net_rate) if latest_history.new_net_rate else None
        old_mrp = float(latest_history.old_mrp) if latest_history.old_mrp else None
        new_mrp = float(latest_history.new_mrp) if latest_history.new_mrp else None
        
        if not old_net or not new_net:
            continue
            
        compression_type = None
        
        if new_net > old_net and (old_mrp == new_mrp or new_mrp is None):
            compression_type = 'buy_rate_up'
            
        elif old_mrp and new_mrp and new_mrp < old_mrp and new_net >= old_net:
            compression_type = 'mrp_drop'
            
        elif new_net > old_net and old_mrp and new_mrp and new_mrp < old_mrp:
            compression_type = 'both'
            
        if not compression_type:
            continue
            
        if old_net > 0:
            compression_pct = ((new_net - old_net) / old_net) * 100
        else:
            compression_pct = 0.0
            
        if compression_pct < 5:
            severity = 'mild'
        elif compression_pct < 15:
            severity = 'moderate'
        else:
            severity = 'severe'
            
        if severity_filter and severity != severity_filter:
            continue
            
        prev_margin = _margin_pct(old_mrp, old_net)
        curr_margin = _margin_pct(new_mrp, new_net)
        margin_delta = None
        if prev_margin is not None and curr_margin is not None:
            margin_delta = round(curr_margin - prev_margin, 2)
            
        results.append({
            "medicine_id": med.id,
            "medicine_name": med.particulars,
            "current_margin_pct": curr_margin,
            "previous_margin_pct": prev_margin,
            "margin_delta_pct": margin_delta,
            "compression_type": compression_type,
            "compression_severity": severity
        })
        
    return results

def get_best_margin_substitutes(db: Session, medicine_id: int) -> dict:
    med = db.get(models.Medicine, medicine_id)
    if not med:
        return {}
        
    subs = graph_service.get_medicine_graph(db, medicine_id)
    if not subs:
        return {}
        
    substitutes_data = subs.get("substitutes", [])
    
    results = []
    unpriced = 0
    for s in substitutes_data:
        sub_med = db.get(models.Medicine, s["medicine_id"])
        margin = _margin_pct(sub_med.mrp, sub_med.net_rate)
        
        if margin is None:
            unpriced += 1
            
        results.append({
            "medicine_id": sub_med.id,
            "name": sub_med.particulars,
            "company": sub_med.company,
            "current_stock": float(sub_med.current_stock or 0),
            "margin_pct": margin,
            "mrp": float(sub_med.mrp) if sub_med.mrp else None,
            "net_rate": float(sub_med.net_rate) if sub_med.net_rate else None,
            "is_in_stock": (sub_med.current_stock or 0) > 0
        })
        
    results.sort(key=lambda x: x["margin_pct"] if x["margin_pct"] is not None else -9999, reverse=True)
    
    return {
        "medicine_id": med.id,
        "name": med.particulars,
        "substitutes": results,
        "unpriced_count": unpriced
    }

def get_distributor_negotiation_report(db: Session) -> list[dict]:
    distributors = db.query(models.Distributor).all()
    results = []
    
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=180)
    
    for dist in distributors:
        bills = db.query(models.Bill).filter(
            models.Bill.distributor_id == dist.id,
            models.Bill.status == 'confirmed'
        ).all()
        
        if not bills:
            continue
            
        med_ids = set()
        for b in bills:
            for item in b.items:
                if item.medicine_id:
                    med_ids.add(item.medicine_id)
                    
        if not med_ids:
            continue
            
        margins = []
        best_med = None
        worst_med = None
        best_margin = -9999
        worst_margin = 9999
        
        for mid in med_ids:
            med = db.get(models.Medicine, mid)
            margin = _margin_pct(med.mrp, med.net_rate)
            if margin is not None:
                margins.append(margin)
                if margin > best_margin:
                    best_margin = margin
                    best_med = med.particulars
                if margin < worst_margin:
                    worst_margin = margin
                    worst_med = med.particulars
                    
        avg_margin = sum(margins) / len(margins) if margins else None
        
        bill_ids = [b.id for b in bills]
        bill_items = db.query(models.BillItem).filter(models.BillItem.bill_id.in_(bill_ids)).all()
        bill_item_ids = [bi.id for bi in bill_items]
        
        rate_changes = db.query(models.RateHistory).filter(
            models.RateHistory.bill_item_id.in_(bill_item_ids),
            models.RateHistory.changed_at >= cutoff_date
        ).all()
        
        change_pcts = []
        for rc in rate_changes:
            if rc.old_net_rate and rc.new_net_rate and float(rc.old_net_rate) > 0:
                change_pct = ((float(rc.new_net_rate) - float(rc.old_net_rate)) / float(rc.old_net_rate)) * 100
                change_pcts.append(change_pct)
                
        price_trend = sum(change_pcts) / len(change_pcts) if change_pcts else None
        
        deal_score = None
        if avg_margin is not None:
            trend = price_trend if price_trend is not None else 0
            score = avg_margin - (0.5 * trend)
            score = max(0, min(100, score))
            deal_score = round(score, 2)
            
        results.append({
            "distributor_id": dist.id,
            "distributor_name": dist.name,
            "avg_margin_across_medicines": round(avg_margin, 2) if avg_margin is not None else None,
            "best_medicine": best_med,
            "worst_medicine": worst_med,
            "price_trend": round(price_trend, 2) if price_trend is not None else None,
            "deal_score": deal_score
        })
        
    results.sort(key=lambda x: x["deal_score"] if x["deal_score"] is not None else -9999, reverse=True)
    return results