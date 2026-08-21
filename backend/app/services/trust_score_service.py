"""
Feature 4 — Supply Chain Trust Score.

This feature is a NEW COMPOSITE SIGNAL built entirely from data already in the system.
It reuses `_leave_one_out_zscores` and GraphEdge supply history rather than building
parallel infrastructure. This ensures that the system works efficiently with the data it
has rather than depending on externally sourced information or complex ML models.

We use deterministic string explanations instead of an LLM (unlike anomaly_explainer_service.py)
because trust scores need to be fully auditable, predictable, and immediately verifiable by the
shop owner. A batch collision or a rate outlier is a concrete mathematical fact, not an interpretation.

The z-score sidedness justification:
- LOW is primary suspicion direction (counterfeit/grey-market) because illicit supply chains
  often introduce fake stock at prices too good to be true.
- HIGH is secondary suspicion (markup abuse), which is often just opportunistic overcharging rather
  than counterfeit stock.

Batch collision weight rationale: collisions (same batch number for the same medicine from different
distributors) are extremely rare and meaningful signals of grey-market blending or counterfeits,
warranting a heavy penalty. Rate variance has many innocent explanations (promotions, older stock),
so it receives a lighter penalty.

NOTE: The following domain event should be added to `app/events/events.py`:
@dataclass(frozen=True, kw_only=True)
class DistributorTrustScoreDroppedEvent(DomainEvent):
    distributor_id: int
    distributor_name: str
    old_score: float
    new_score: float
    reasons: list[str]
    db: Session

NOTE: The following model should be added to `app/models.py`:
class DistributorTrustScore(Base):
    __tablename__ = "distributor_trust_scores"
    id = Column(Integer, primary_key=True, index=True)
    distributor_id = Column(Integer, ForeignKey("distributors.id"), nullable=False, unique=True, index=True)
    score = Column(Numeric(5, 2), nullable=False)
    confidence = Column(String(20), nullable=False)
    last_computed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    distributor = relationship("Distributor")
"""

import logging
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from typing import Optional

from sqlalchemy.orm import Session

from app import models
from app.services.anomaly_service import _leave_one_out_zscores
from app.services.matcher import normalize
from app.services.audit_service import log_event
from app.events.bus import event_bus
from app.events import events

logger = logging.getLogger(__name__)

Z_SCORE_THRESHOLD = 2.0  # From anomaly_service
HIGH_RISK_THRESHOLD = 40.0


def detect_batch_collisions(db: Session, days: int = 365) -> list[dict]:
    """
    Find every (normalized_batch_no, medicine_id) pair from MedicineBatch that
    appears across 2+ distinct distributor_ids within the confirmed bills window.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    query = (
        db.query(models.MedicineBatch, models.Bill, models.Medicine)
        .join(models.BillItem, models.MedicineBatch.bill_item_id == models.BillItem.id)
        .join(models.Bill, models.BillItem.bill_id == models.Bill.id)
        .join(models.Medicine, models.MedicineBatch.medicine_id == models.Medicine.id)
        .filter(models.Bill.status == 'confirmed')
        .filter((models.Bill.invoice_date >= cutoff) | (models.Bill.uploaded_at >= cutoff))
    )
    
    batches = query.all()
    groups = defaultdict(list)
    distributors = {d.id: d.name for d in db.query(models.Distributor).all()}
    
    for mb, bill, med in batches:
        if not mb.batch_no:
            continue
        norm_batch = normalize(mb.batch_no)
        if not norm_batch:
            continue
            
        dist_id = bill.distributor_id
        if dist_id is None:
            continue
            
        date_seen = bill.invoice_date or bill.uploaded_at
        
        groups[(med.id, med.particulars, norm_batch)].append({
            "distributor_id": dist_id,
            "distributor_name": distributors.get(dist_id, "Unknown"),
            "date": date_seen
        })
        
    results = []
    for (med_id, med_name, norm_batch), sightings in groups.items():
        distinct_dists = {s["distributor_id"] for s in sightings}
        if len(distinct_dists) >= 2:
            distributor_names = list({s["distributor_name"] for s in sightings})
            dates = [s["date"] for s in sightings if s["date"]]
            
            results.append({
                "medicine_id": med_id,
                "medicine_name": med_name,
                "normalized_batch_no": norm_batch,
                "distributor_ids": list(distinct_dists),
                "distributor_names": distributor_names,
                "first_seen": min(dates) if dates else None,
                "last_seen": max(dates) if dates else None,
                "occurrence_count": len(sightings)
            })
            
    return results


def compute_rate_consistency(db: Session, medicine_id: int, days: int = 365) -> dict:
    """
    Groups confirmed BillItem computed cost by distributor_id and computes the average rate.
    Flags outliers using a leave-one-out z-score to identify consistent rate anomalies.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    query = (
        db.query(models.BillItem, models.Bill)
        .join(models.Bill, models.BillItem.bill_id == models.Bill.id)
        .filter(models.BillItem.medicine_id == medicine_id)
        .filter(models.Bill.status == 'confirmed')
        .filter((models.Bill.invoice_date >= cutoff) | (models.Bill.uploaded_at >= cutoff))
    )
    
    items = query.all()
    dist_rates = defaultdict(list)
    for bi, bill in items:
        if bi.computed_cost_per_unit is not None and bill.distributor_id is not None:
            dist_rates[bill.distributor_id].append(float(bi.computed_cost_per_unit))
            
    distributors = {d.id: d.name for d in db.query(models.Distributor).all()}
    
    dist_averages = []
    for dist_id, rates in dist_rates.items():
        dist_averages.append({
            "distributor_id": dist_id,
            "distributor_name": distributors.get(dist_id, "Unknown"),
            "avg_rate": sum(rates) / len(rates),
        })
        
    if len(dist_averages) < 3:
        return {
            "has_sufficient_data": False,
            "distributor_averages": []
        }
        
    rates_list = [d["avg_rate"] for d in dist_averages]
    z_scores = _leave_one_out_zscores(rates_list)
    
    results = []
    for i, d in enumerate(dist_averages):
        z = z_scores.get(i, 0.0)
        is_outlier = abs(z) > Z_SCORE_THRESHOLD
        
        direction = None
        if is_outlier:
            direction = "low" if z < 0 else "high"
            
        d["z_score"] = z
        d["is_outlier"] = is_outlier
        d["direction"] = direction
        results.append(d)
        
    return {
        "has_sufficient_data": True,
        "distributor_averages": results
    }


def compute_trust_score(db: Session, distributor_id: int, medicine_id: Optional[int] = None) -> dict:
    """
    Computes a composite supply chain trust score (0-100) for a distributor.
    Penalties are applied for batch collisions (severe) and rate outliers (moderate).
    """
    score = 100
    contributing_factors = []
    
    dist = db.get(models.Distributor, distributor_id)
    dist_name = dist.name if dist else "Unknown"
    
    bill_count = (
        db.query(models.Bill)
        .filter(models.Bill.distributor_id == distributor_id)
        .filter(models.Bill.status == 'confirmed')
        .count()
    )
    if bill_count >= 5:
        confidence = "high"
    elif bill_count >= 3:
        confidence = "medium"
    else:
        confidence = "low"
        
    all_collisions = detect_batch_collisions(db)
    my_collisions = [c for c in all_collisions if distributor_id in c["distributor_ids"]]
    
    batch_penalty = 0
    for c in my_collisions:
        batch_penalty += 25
        other_dists = [name for name in c["distributor_names"] if name != dist_name]
        other_names = ", ".join(other_dists)
        contributing_factors.append(f"1 batch number shared with {other_names} for {c['medicine_name']}")
        
    batch_penalty = min(batch_penalty, 50)
    score -= batch_penalty
    
    query = (
        db.query(models.BillItem.medicine_id)
        .join(models.Bill, models.BillItem.bill_id == models.Bill.id)
        .filter(models.Bill.distributor_id == distributor_id)
        .filter(models.Bill.status == 'confirmed')
        .distinct()
    )
    med_ids = [r[0] for r in query.all() if r[0]]
    if medicine_id is not None:
        if medicine_id in med_ids:
            med_ids = [medicine_id]
        else:
            med_ids = []
            
    rate_penalty = 0
    rate_outlier_summary = []
    
    for mid in med_ids:
        rc = compute_rate_consistency(db, mid)
        if rc["has_sufficient_data"]:
            for d in rc["distributor_averages"]:
                if d["distributor_id"] == distributor_id and d["is_outlier"]:
                    med = db.get(models.Medicine, mid)
                    med_name = med.particulars if med else "Unknown"
                    if d["direction"] == "low":
                        rate_penalty += 15
                        contributing_factors.append(f"Unusually low price for {med_name} compared to market")
                    elif d["direction"] == "high":
                        rate_penalty += 8
                        contributing_factors.append(f"Unusually high price for {med_name} compared to market")
                        
                    rate_outlier_summary.append({
                        "medicine_id": mid,
                        "medicine_name": med_name,
                        "direction": d["direction"],
                        "z_score": d["z_score"]
                    })
                    
    rate_penalty = min(rate_penalty, 30)
    score -= rate_penalty
    score = max(score, 0)
    
    try:
        TrustScoreModel = getattr(models, "DistributorTrustScore")
        ts = db.query(TrustScoreModel).filter(TrustScoreModel.distributor_id == distributor_id).first()
        old_score = float(ts.score) if ts else 100.0
        
        if not ts:
            ts = TrustScoreModel(distributor_id=distributor_id, score=score, confidence=confidence)
            db.add(ts)
        else:
            ts.score = score
            ts.confidence = confidence
            ts.computed_at = datetime.now(timezone.utc)
            
        db.flush()
        
        if old_score >= HIGH_RISK_THRESHOLD and score < HIGH_RISK_THRESHOLD:
            DroppedEvent = getattr(events, "DistributorTrustScoreDroppedEvent", None)
            if DroppedEvent:
                evt = DroppedEvent(
                    distributor_id=distributor_id,
                    distributor_name=dist_name,
                    old_score=old_score,
                    new_score=score,
                    reasons=contributing_factors,
                    db=db
                )
                event_bus.publish(evt)
                
            log_event(db, "distributor_trust_score_drop", distributor_id, {
                "distributor_id": distributor_id,
                "old_score": old_score,
                "new_score": score,
                "reasons": contributing_factors
            })
            
    except AttributeError:
        # TrustScoreModel is not defined yet; expected if models.py is updated separately.
        pass
        
    return {
        "distributor_id": distributor_id,
        "distributor_name": dist_name,
        "score": score,
        "confidence": confidence,
        "contributing_factors": contributing_factors,
        "batch_collisions": my_collisions,
        "rate_outlier_summary": rate_outlier_summary
    }


def compute_all_distributor_scores(db: Session) -> list[dict]:
    """
    Computes trust scores for all distributors and sorts them by lowest score first.
    """
    dists = db.query(models.Distributor).all()
    results = [compute_trust_score(db, d.id) for d in dists]
    results.sort(key=lambda x: x["score"])
    return results
