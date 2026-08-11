from datetime import date, datetime, timedelta
from typing import Dict, Any, List
import math

from sqlalchemy.orm import Session
from sqlalchemy import func

from app import models
from app.services.forecast_service import get_demand_forecast

def generate_purchase_order(db: Session) -> dict:
    """
    Generates a smart purchase order grouped by distributor.
    Uses 14-day demand forecast, current stock, near-expiry stock,
    and lead times to determine what to order.
    """
    # 1. Get medicines that have sales history (to avoid processing all medicines)
    sale_med_ids = [m_id for (m_id,) in db.query(models.Sale.medicine_id).distinct().all()]
    if not sale_med_ids:
        return {
            "generated_at": datetime.utcnow().isoformat(),
            "total_estimated_cost": 0.0,
            "items_count": 0,
            "groups": []
        }

    # 2. Batch fetch Medicines
    medicines = db.query(models.Medicine).filter(models.Medicine.id.in_(sale_med_ids)).all()
    
    # 3. Batch fetch near-expiry batches (expiry < today + 30 days)
    today = date.today()
    thirty_days_from_now = today + timedelta(days=30)
    expiring_batches = db.query(models.MedicineBatch).filter(
        models.MedicineBatch.medicine_id.in_(sale_med_ids),
        models.MedicineBatch.expiry_date != None,
        models.MedicineBatch.expiry_date < thirty_days_from_now
    ).all()
    
    near_expiry_by_med = {}
    for b in expiring_batches:
        near_expiry_by_med[b.medicine_id] = near_expiry_by_med.get(b.medicine_id, 0.0) + float(b.qty_received)
        
    # 4. Batch fetch last distributor and last net rate
    # Using rate history for net rate and most recent confirmed bill item for distributor
    # Subqueries to get the latest
    latest_bill_items = (
        db.query(
            models.BillItem.medicine_id,
            models.Bill.distributor_id,
            models.Distributor.name.label("distributor_name")
        )
        .join(models.Bill, models.BillItem.bill_id == models.Bill.id)
        .join(models.Distributor, models.Bill.distributor_id == models.Distributor.id)
        .filter(
            models.Bill.status == "confirmed",
            models.BillItem.medicine_id.in_(sale_med_ids)
        )
        .order_by(models.BillItem.medicine_id, models.Bill.invoice_date.desc())
        .all()
    )
    
    dist_by_med = {}
    for item in latest_bill_items:
        # Since we ordered by desc, the first one we see or last one we see?
        # Actually sqlalchemy order_by + all() doesn't group by. We need a dictionary that keeps the first seen (most recent)
        if item.medicine_id not in dist_by_med:
            dist_by_med[item.medicine_id] = item.distributor_name

    items = []
    
    for med in medicines:
        # Get forecast
        forecast_result = get_demand_forecast(db, med.id, periods=14, history_days=180)
        
        if not forecast_result.get("has_sufficient_data"):
            # skip if not enough data
            continue
            
        forecasts = forecast_result.get("forecast", [])
        demand_14d = sum(f["predicted_qty"] for f in forecasts)
        
        near_expiry_qty = near_expiry_by_med.get(med.id, 0.0)
        usable_stock = max(0.0, float(med.current_stock) - near_expiry_qty)
        projected_need = demand_14d - usable_stock
        
        if projected_need <= 0:
            continue
            
        # compute order qty with safety buffer (from smart threshold)
        safety_buffer = float(med.suggested_low_stock_threshold or 0)
        order_qty = math.ceil(projected_need) + safety_buffer
        if order_qty <= 0:
            continue
            
        last_net_rate = float(med.net_rate or 0)
        estimated_cost = order_qty * last_net_rate
        priority_score = projected_need / demand_14d if demand_14d > 0 else 0
        
        priority_label = "low"
        if priority_score > 0.8:
            priority_label = "high"
        elif priority_score > 0.4:
            priority_label = "medium"
            
        avg_daily = float(med.avg_daily_sales_30d or 0)
        days_of_stock_remaining = usable_stock / avg_daily if avg_daily > 0 else float('inf')
        if days_of_stock_remaining == float('inf'):
            days_of_stock_remaining = -1
            
        items.append({
            "medicine_id": med.id,
            "medicine_name": med.particulars,
            "order_qty": order_qty,
            "unit": med.unit,
            "last_net_rate": last_net_rate,
            "estimated_cost": estimated_cost,
            "priority_score": round(priority_score, 2),
            "priority_label": priority_label,
            "reason": f"Need {round(projected_need, 1)} units to cover 14 days",
            "last_distributor_name": dist_by_med.get(med.id, "Unknown"),
            "demand_14d": round(demand_14d, 1),
            "usable_stock": round(usable_stock, 1),
            "near_expiry_qty": near_expiry_qty,
            "days_of_stock_remaining": round(days_of_stock_remaining, 1)
        })

    # Group by distributor
    groups_map = {}
    total_cost = 0.0
    for item in items:
        d_name = item["last_distributor_name"]
        if d_name not in groups_map:
            groups_map[d_name] = []
        groups_map[d_name].append(item)
        total_cost += item["estimated_cost"]
        
    for k in groups_map:
        groups_map[k].sort(key=lambda x: x["priority_score"], reverse=True)

    result_groups = [{"distributor_name": k, "items": v} for k, v in groups_map.items()]
    
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "total_estimated_cost": round(total_cost, 2),
        "items_count": len(items),
        "groups": result_groups
    }
