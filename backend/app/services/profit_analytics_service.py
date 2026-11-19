"""
Profit margin analytics - a NEW, small, focused service (Pillar 2 addition).
No existing function computed profit margin, so this is added as its own
module rather than bolted inline into copilot_service.py, matching this
codebase's one-module-per-concern convention (see cost_calculator.py,
matcher.py, etc. for the same pattern).

Issue 5: sale-derived/realized profit metrics prefer persisted sale-time
snapshots (not current Medicine prices), with safe fallback for legacy rows.
Catalog/rate-history analytics that are inherently current (e.g. compression,
substitute recommendations) continue to use current/rate data.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy.orm import Session

from app import models
from app.services import graph_service

Q2 = Decimal("0.01")


def _d(value) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _q2(value: Decimal) -> Decimal:
    return _d(value).quantize(Q2, rounding=ROUND_HALF_UP)


def _margin_pct(mrp, net_rate) -> Optional[float]:
    mrp_d = _d(mrp)
    if mrp_d <= 0 or mrp is None or net_rate is None:
        return None
    pct = ((_d(mrp) - _d(net_rate)) / mrp_d) * Decimal("100")
    return float(_q2(pct))


def _sale_line_realized(sale: models.Sale, medicine: Optional[models.Medicine] = None) -> Optional[dict]:
    """Return realized totals/profit for a sale line from snapshots, with legacy fallback."""
    qty = _d(getattr(sale, "qty_sold", None))
    if qty <= 0:
        return None

    med = medicine or getattr(sale, "medicine", None)

    mrp = getattr(sale, "unit_mrp_snapshot", None)
    cost = getattr(sale, "unit_cost_snapshot", None)
    line_total = getattr(sale, "line_total", None)
    line_profit = getattr(sale, "line_profit", None)
    line_subtotal = getattr(sale, "line_subtotal", None)
    line_tax = getattr(sale, "line_tax_amount", None)

    if mrp is None and med is not None:
        mrp = getattr(med, "mrp", None)
    if cost is None and med is not None:
        cost = getattr(med, "net_rate", None)

    mrp_d = _d(mrp) if mrp is not None else None
    cost_d = _d(cost) if cost is not None else None

    if line_total is None:
        if mrp_d is None:
            return None
        line_total = _q2(mrp_d * qty)
    else:
        line_total = _q2(_d(line_total))

    if line_profit is None:
        if mrp_d is None or cost_d is None:
            line_profit = None
        else:
            line_profit = _q2((mrp_d - cost_d) * qty)
    else:
        line_profit = _q2(_d(line_profit))

    return {
        "sale_id": sale.id,
        "medicine_id": sale.medicine_id,
        "qty": qty,
        "line_total": line_total,
        "line_profit": line_profit,
        "line_subtotal": _q2(_d(line_subtotal)) if line_subtotal is not None else None,
        "line_tax_amount": _q2(_d(line_tax)) if line_tax is not None else None,
        "unit_mrp": mrp_d,
        "unit_cost": cost_d,
    }


def _realized_margin_pct(line_total: Decimal, line_profit: Optional[Decimal]) -> Optional[Decimal]:
    if line_profit is None or line_total is None or line_total <= 0:
        return None
    return _q2((line_profit / line_total) * Decimal("100"))


def get_profit_margin_analysis(db: Session, tenant_id: int, condition: Optional[str] = None) -> dict:
    """
    Average profit margin % across the whole shop's priced catalog, and
    optionally for medicines associated with a specific condition (via
    PharmaGraph's TREATS edges) so the two can be compared.

    Issue 5: realized/sale-derived metrics prefer persisted sale-time snapshots
    (not current Medicine prices), with legacy fallback for older rows. Catalog
    metrics remain available for backward compatibility.
    """
    all_medicines = db.query(models.Medicine).filter(
        models.Medicine.tenant_id == tenant_id,
        models.Medicine.mrp.isnot(None),
        models.Medicine.net_rate.isnot(None),
        models.Medicine.mrp > 0,
    ).all()

    shop_margins = [m for m in (_margin_pct(med.mrp, med.net_rate) for med in all_medicines) if m is not None]
    catalog_shop_avg = round(sum(shop_margins) / len(shop_margins), 2) if shop_margins else None

    # Realized (sales snapshot) shop margin
    sales = db.query(models.Sale).filter(models.Sale.tenant_id == tenant_id).all()
    realized_margins = []
    realized_revenue = Decimal("0.00")
    realized_profit = Decimal("0.00")
    for sale in sales:
        line = _sale_line_realized(sale, getattr(sale, "medicine", None))
        if not line:
            continue
        realized_revenue += line["line_total"]
        if line["line_profit"] is not None:
            realized_profit += line["line_profit"]
        m = _realized_margin_pct(line["line_total"], line["line_profit"])
        if m is not None:
            realized_margins.append(m)
    realized_shop_avg = float(_q2(sum(realized_margins, Decimal("0")) / Decimal(len(realized_margins)))) if realized_margins else None
    realized_overall_margin = float(_realized_margin_pct(realized_revenue, realized_profit)) if realized_revenue > 0 and realized_margins is not None else None

    shop_avg = realized_shop_avg if realized_shop_avg is not None else catalog_shop_avg
    result = {
        "shop_average_margin_pct": shop_avg,
        "shop_priced_medicine_count": len(shop_margins),
        # Additive/backward-compatible fields
        "catalog_shop_average_margin_pct": catalog_shop_avg,
        "realized_shop_average_margin_pct": realized_shop_avg,
        "realized_overall_margin_pct": realized_overall_margin,
        "realized_sales_line_count": len(realized_margins),
        "realized_revenue": float(_q2(realized_revenue)),
        "realized_profit": float(_q2(realized_profit)),
        "source": "sale_snapshots" if realized_shop_avg is not None else "catalog",
    }

    if condition:
        condition_medicines = graph_service.get_medicines_for_condition(db, condition, in_stock_only=False)
        matched_ids = {c["medicine_id"] for c in condition_medicines}
        matched = [m for m in all_medicines if m.id in matched_ids]
        cond_margins = [x for x in (_margin_pct(m.mrp, m.net_rate) for m in matched) if x is not None]

        # Realized margin for condition-related medicines (from sale snapshots)
        realized_cond = []
        for sale in sales:
            if sale.medicine_id not in matched_ids:
                continue
            line = _sale_line_realized(sale, getattr(sale, "medicine", None))
            if not line:
                continue
            m = _realized_margin_pct(line["line_total"], line["line_profit"])
            if m is not None:
                realized_cond.append(m)
        realized_cond_avg = float(_q2(sum(realized_cond, Decimal("0")) / Decimal(len(realized_cond)))) if realized_cond else None
        catalog_cond_avg = round(sum(cond_margins) / len(cond_margins), 2) if cond_margins else None
        cond_avg = realized_cond_avg if realized_cond_avg is not None else catalog_cond_avg

        result["condition"] = condition
        result["condition_average_margin_pct"] = cond_avg
        result["condition_priced_medicine_count"] = len(cond_margins)
        result["catalog_condition_average_margin_pct"] = catalog_cond_avg
        result["realized_condition_average_margin_pct"] = realized_cond_avg
        result["condition_realized_sales_line_count"] = len(realized_cond)
        if shop_avg is not None and cond_avg is not None:
            result["difference_vs_shop_average_pct"] = round(cond_avg - shop_avg, 2)

    return result

from datetime import datetime, timedelta, timezone

def detect_margin_compression(db: Session, tenant_id: int, days: int = 90, severity_filter: Optional[str] = None) -> list[dict]:
    # For each medicine: check last 2 RateHistory entries within days.
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    medicines = db.query(models.Medicine).filter(models.Medicine.tenant_id == tenant_id).all()
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

def get_best_margin_substitutes(db: Session, tenant_id: int, medicine_id: int) -> dict:
    med = db.query(models.Medicine).filter_by(id=medicine_id, tenant_id=tenant_id).first()
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
        if sub_med is None:
            continue
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

def get_distributor_negotiation_report(db: Session, tenant_id: int) -> list[dict]:
    distributors = db.query(models.Distributor).filter(models.Distributor.tenant_id == tenant_id).all()
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
            if med is None:
                continue
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