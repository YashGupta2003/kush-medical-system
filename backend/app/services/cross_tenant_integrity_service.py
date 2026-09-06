import json
from datetime import datetime, timedelta, timezone, date
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app import models
from app.services.matcher import normalize
from app.services.audit_service import log_event
from app.events.bus import event_bus
from app.events.events import CrossTenantCollisionDetectedEvent


def normalize_batch(raw: str) -> str:
    """
    Reuse the exact same normalization logic already used in trust_score_service.py.
    """
    if not raw:
        return ""
    return normalize(raw)


def scan_cross_tenant_collisions(db: Session, days: int = 365) -> Dict[str, Any]:
    """
    Scan for cases where the SAME normalized batch for the SAME normalized medicine name
    appears across multiple distinct tenants from different distributors.
    
    NOTE: We DELIBERATELY DO NOT filter by tenant_id in this query. This is a system-wide
    cross-tenant integrity scan designed to detect counterfeit/grey-market batches that
    are circulating in the region. No single pharmacy's own bills could ever reveal this.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Query without tenant_id filter intentionally.
    query = (
        db.query(
            models.Bill.tenant_id,
            models.Distributor.name.label("distributor_name"),
            models.BillItem.batch,
            models.Medicine.particulars,
            models.Bill.uploaded_at,
            models.Bill.invoice_date,
        )
        .join(models.BillItem, models.BillItem.bill_id == models.Bill.id)
        .join(models.Medicine, models.BillItem.medicine_id == models.Medicine.id)
        .join(models.Distributor, models.Bill.distributor_id == models.Distributor.id)
        .filter(
            models.Bill.status == 'confirmed',
            models.BillItem.batch != None,
            models.BillItem.batch != '',
            or_(models.Bill.invoice_date >= cutoff.date(), models.Bill.uploaded_at >= cutoff)
        )
    )

    # Group in memory to handle normalization securely without complex SQL functions.
    # groups[ (norm_batch, norm_med) ] = [ (tenant_id, dist_name, timestamp), ... ]
    groups: Dict[tuple, List[tuple]] = {}
    
    for row in query.all():
        if not row.batch:
            continue
            
        norm_batch = normalize_batch(row.batch)
        norm_med = normalize(row.particulars)
        
        if not norm_batch or not norm_med:
            continue
            
        timestamp = row.invoice_date if row.invoice_date else row.uploaded_at
        if isinstance(timestamp, date) and not isinstance(timestamp, datetime):
            timestamp = datetime(timestamp.year, timestamp.month, timestamp.day, tzinfo=timezone.utc)
        elif timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
            
        key = (norm_batch, norm_med, row.particulars) # keeping original particular for display
        
        groups.setdefault(key, []).append((row.tenant_id, normalize(row.distributor_name), row.distributor_name, timestamp))

    new_alerts = 0
    updated_alerts = 0

    for (norm_batch, norm_med, med_display), items in groups.items():
        tenant_ids = set()
        distributor_names = set()
        display_dists = set()
        first_seen = None
        last_seen = None
        
        for t_id, norm_dist, dist, ts in items:
            tenant_ids.add(t_id)
            distributor_names.add(norm_dist)
            display_dists.add(dist)
            
            if first_seen is None or ts < first_seen:
                first_seen = ts
            if last_seen is None or ts > last_seen:
                last_seen = ts

        # A group is a genuine alert ONLY if it spans >= 2 distinct tenant_ids AND >= 2 distinct distributor names.
        if len(tenant_ids) >= 2 and len(distributor_names) >= 2:
            existing_alert = (
                db.query(models.CrossTenantBatchAlert)
                .filter_by(normalized_batch_no=norm_batch, medicine_name=norm_med)
                .first()
            )
            
            tenant_ids_list = list(tenant_ids)
            display_dists_list = list(display_dists)
            
            if existing_alert:
                existing_alert.occurrence_count = len(items)
                existing_alert.tenant_ids = json.dumps(tenant_ids_list)
                existing_alert.distributor_names = json.dumps(display_dists_list)
                
                if first_seen and (existing_alert.first_seen is None or first_seen < existing_alert.first_seen.replace(tzinfo=timezone.utc)):
                    existing_alert.first_seen = first_seen
                if last_seen and (existing_alert.last_seen is None or last_seen > existing_alert.last_seen.replace(tzinfo=timezone.utc)):
                    existing_alert.last_seen = last_seen
                
                updated_alerts += 1
            else:
                new_alert = models.CrossTenantBatchAlert(
                    medicine_name=norm_med,
                    normalized_batch_no=norm_batch,
                    tenant_ids=json.dumps(tenant_ids_list),
                    distributor_names=json.dumps(display_dists_list),
                    occurrence_count=len(items),
                    first_seen=first_seen,
                    last_seen=last_seen,
                    status='open',
                    severity='high'
                )
                db.add(new_alert)
                db.flush()
                
                # Publish event
                event_bus.publish(CrossTenantCollisionDetectedEvent(
                    alert_id=new_alert.id,
                    medicine_name=med_display,
                    normalized_batch_no=norm_batch,
                    tenant_ids=tenant_ids_list,
                    distributor_names=display_dists_list,
                    db=db
                ))
                new_alerts += 1

    db.commit()
    
    total_open = db.query(models.CrossTenantBatchAlert).filter_by(status='open').count()
    
    return {
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "new_alerts": new_alerts,
        "updated_alerts": updated_alerts,
        "total_open_alerts": total_open
    }


def get_alerts_for_tenant(db: Session, tenant_id: int, status: str = "open") -> List[Dict[str, Any]]:
    # We load all alerts matching the status and filter by tenant_id in memory 
    # since tenant_ids is JSON text.
    alerts = db.query(models.CrossTenantBatchAlert).filter_by(status=status).all()
    results = []
    
    for alert in alerts:
        t_ids = json.loads(alert.tenant_ids)
        if tenant_id in t_ids:
            dists = json.loads(alert.distributor_names)
            results.append({
                "id": alert.id,
                "medicine_name": alert.medicine_name,
                "normalized_batch_no": alert.normalized_batch_no,
                "distributor_names": dists,
                "occurrence_count": alert.occurrence_count,
                "first_seen": alert.first_seen,
                "last_seen": alert.last_seen,
                "severity": alert.severity,
                "status": alert.status,
                "other_pharmacies_involved": len(t_ids) - 1
            })
            
    return results


def update_alert_status(db: Session, alert_id: int, tenant_id: int, new_status: str) -> Dict[str, Any]:
    if new_status not in ["open", "reviewed", "dismissed"]:
        raise ValueError("Invalid status")
        
    alert = db.get(models.CrossTenantBatchAlert, alert_id)
    if not alert:
        raise ValueError("Alert not found")
        
    t_ids = json.loads(alert.tenant_ids)
    if tenant_id not in t_ids:
        raise ValueError("Tenant not involved in this alert")
        
    alert.status = new_status
    
    # Log this status change
    log_event(db, "cross_tenant_alert_reviewed", alert.id, {
        "tenant_id": tenant_id,
        "new_status": new_status,
        "medicine_name": alert.medicine_name,
        "batch": alert.normalized_batch_no
    })
    
    db.commit()
    
    return {"id": alert.id, "status": alert.status}
