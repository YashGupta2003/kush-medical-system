"""
Syndromic Surveillance — Regional Health Pulse.

Privacy-by-Construction: this module ONLY reads/writes SurveillanceDailyCount
rows (pre-aggregated daily counts per condition). It never stores which
customer, which specific medicine, or which sale triggered the count —
that data stays in the existing Sale/StockLedger tables and never crosses
into this surveillance layer.

Integration with existing Pillars:
  - Pillar 1 (PharmaGraph): get_conditions_for_medicine() walks
    medicine → CONTAINS → salt → TREATS → condition edges to determine
    which health conditions a sold medicine maps to.
  - Pillar 6 (Anomaly Detection): _leave_one_out_zscores() from
    anomaly_service is reused as the spike detection primitive — the same
    statistical method that detects unusual price jumps and stock
    adjustments, applied here to daily condition counts.
"""
import math
from datetime import date, datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import SurveillanceDailyCount
from app.services import graph_service
from app.services import anomaly_service
from app.events.bus import event_bus
from app.events.events import SurveillanceSpikeDetectedEvent

def get_conditions_for_medicine(db: Session, medicine_id: int) -> List[str]:
    """Walk PharmaGraph: medicine → CONTAINS → salt → TREATS → condition."""
    conditions = set()
    # medicine -> CONTAINS -> salt
    salts = graph_service.get_neighbors(db, "medicine", str(medicine_id), "CONTAINS")
    for salt in salts:
        # salt -> TREATS -> condition
        conds = graph_service.get_neighbors(db, "salt", salt["id"], "TREATS")
        for cond in conds:
            conditions.add(cond["id"])
    return list(conditions)

def record_sale_signal(db: Session, medicine_id: int, qty_sold: int, sale_date: date = None) -> None:
    if sale_date is None:
        sale_date = date.today()
    
    conditions = get_conditions_for_medicine(db, medicine_id)
    if not conditions:
        return
        
    for condition in conditions:
        record = db.query(SurveillanceDailyCount).filter(
            SurveillanceDailyCount.condition_name == condition,
            SurveillanceDailyCount.count_date == sale_date
        ).first()
        
        if record:
            record.otc_units += qty_sold
        else:
            record = SurveillanceDailyCount(
                condition_name=condition,
                count_date=sale_date,
                otc_units=qty_sold
            )
            db.add(record)
    
    db.flush()

def get_trend_data(db: Session, condition_name: str, days: int = 30) -> List[Dict[str, Any]]:
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)
    
    records = db.query(SurveillanceDailyCount).filter(
        SurveillanceDailyCount.condition_name == condition_name,
        SurveillanceDailyCount.count_date >= start_date,
        SurveillanceDailyCount.count_date <= end_date
    ).all()
    
    record_dict = {r.count_date: r.otc_units for r in records}
    
    trend = []
    for i in range(days):
        d = start_date + timedelta(days=i)
        trend.append({
            "date": d.isoformat(),
            "otc_units": record_dict.get(d, 0)
        })
    return trend

def detect_spikes(db: Session, days: int = 14, z_threshold: float = 2.0) -> List[Dict[str, Any]]:
    # Get all distinct conditions in the window
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)
    
    conditions = db.query(SurveillanceDailyCount.condition_name).filter(
        SurveillanceDailyCount.count_date >= start_date,
        SurveillanceDailyCount.count_date <= end_date
    ).distinct().all()
    
    spikes = []
    
    for (cond,) in conditions:
        trend = get_trend_data(db, cond, days=days)
        counts = [t["otc_units"] for t in trend]
        
        if sum(counts) == 0 or len(counts) < 3:
            continue

        # Skip conditions with zero variance — all identical counts
        # can't have a meaningful spike (_leave_one_out_zscores returns
        # inf when std=0, which would false-positive every condition).
        if max(counts) == min(counts):
            continue
            
        z_scores = anomaly_service._leave_one_out_zscores(counts)
        
        for i, z in z_scores.items():
            if math.isfinite(z) and z >= z_threshold and counts[i] > 0:
                is_recent = (i >= len(counts) - 2)
                if is_recent:
                    avg = (sum(counts) - counts[i]) / max(1, (len(counts) - 1))
                    spike_data = {
                        "condition_name": cond,
                        "spike_date": trend[i]["date"],
                        "count": counts[i],
                        "z_score": float(z),
                        "avg_count": float(avg)
                    }
                    spikes.append(spike_data)
                    
                    event = SurveillanceSpikeDetectedEvent(
                        condition_name=cond,
                        spike_date=trend[i]["date"],
                        count=counts[i],
                        z_score=float(z),
                        avg_count=float(avg),
                        db=db
                    )
                    event_bus.publish(event)
    
    return spikes

def get_all_conditions_summary(db: Session, days: int = 7) -> List[Dict[str, Any]]:
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)
    
    conditions = db.query(SurveillanceDailyCount.condition_name).filter(
        SurveillanceDailyCount.count_date >= start_date,
        SurveillanceDailyCount.count_date <= end_date
    ).distinct().all()
    
    summaries = []
    
    for (cond,) in conditions:
        trend = get_trend_data(db, cond, days=days)
        counts = [t["otc_units"] for t in trend]
        total = sum(counts)
        avg = total / days
        
        z_scores = anomaly_service._leave_one_out_zscores(counts)
        has_spike = False
        latest_z = None
        n = len(counts)
        # Guard against inf/NaN from zero-variance data (std=0)
        if n >= 1 and math.isfinite(z_scores.get(n - 1, float('inf'))):
            latest_z = float(z_scores[n - 1])
            if latest_z >= 2.0 and counts[-1] > 0:
                has_spike = True
            elif n >= 2 and math.isfinite(z_scores.get(n - 2, float('inf'))) and z_scores[n - 2] >= 2.0 and counts[-2] > 0:
                has_spike = True
                latest_z = float(z_scores[n - 2])
                
        summaries.append({
            "condition_name": cond,
            "total_units_7d": total,
            "avg_daily": float(avg),
            "has_spike": has_spike,
            "latest_z_score": latest_z
        })
        
    return summaries
