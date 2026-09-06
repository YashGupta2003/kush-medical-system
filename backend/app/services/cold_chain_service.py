"""
Cold-Chain Compliance Ledger.

Logs fridge temperatures, detects excursions, computes compliance rates,
and integrates with:
  - TrustChain (Pillar 4): every reading is logged as a tamper-evident
    audit entry via audit_service.log_event — temperature compliance is a
    regulatory requirement where the audit trail itself needs to be
    trustworthy.
  - EventBus: ColdChainExcursionEvent fires on out-of-range readings,
    triggering notifications to owners.
  - NetworkListing (Pillar 5): when an excursion is detected, batches
    stored in that unit that are marked is_cold_chain=True can be flagged
    as compromised for potential redistribution via the network.

Design decision: readings are staff-accessible (any logged-in user can
log a temperature reading — this is a routine operational task). Compliance
reporting and unit management are owner-only (financial/regulatory scope).
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from app.models import ColdChainUnit, ColdChainReading, MedicineBatch, Medicine, User
from app.events.events import ColdChainExcursionEvent
from app.events.bus import event_bus
from app.services import audit_service


def create_unit(db: Session, unit_label: str, location_note: Optional[str] = None, min_temp_c: float = 2.0, max_temp_c: float = 8.0) -> ColdChainUnit:
    unit = ColdChainUnit(
        unit_label=unit_label,
        location_note=location_note,
        min_temp_c=min_temp_c,
        max_temp_c=max_temp_c,
        is_active=True
    )
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return unit

def list_units(db: Session, active_only: bool = True) -> List[ColdChainUnit]:
    query = db.query(ColdChainUnit)
    if active_only:
        query = query.filter(ColdChainUnit.is_active == True)
    return query.all()

def get_unit(db: Session, unit_id: int) -> Optional[ColdChainUnit]:
    return db.query(ColdChainUnit).filter(ColdChainUnit.id == unit_id).first()

def update_unit(db: Session, unit_id: int, **kwargs) -> Optional[ColdChainUnit]:
    unit = get_unit(db, unit_id)
    if not unit:
        return None
    for key, value in kwargs.items():
        if value is not None and hasattr(unit, key):
            setattr(unit, key, value)
    db.commit()
    db.refresh(unit)
    return unit

def record_reading(db: Session, unit_id: int, temp_c: float, recorded_by_user_id: Optional[int] = None, note: Optional[str] = None) -> ColdChainReading:
    unit = get_unit(db, unit_id)
    if not unit:
        raise ValueError(f"ColdChainUnit {unit_id} not found.")

    is_excursion = False
    if temp_c < float(unit.min_temp_c) or temp_c > float(unit.max_temp_c):
        is_excursion = True

    reading = ColdChainReading(
        unit_id=unit_id,
        recorded_temp_c=temp_c,
        recorded_by_user_id=recorded_by_user_id,
        note=note,
        is_excursion=is_excursion
    )
    db.add(reading)
    db.commit()
    db.refresh(reading)

    audit_service.log_event(
        db=db,
        event_type="cold_chain_reading",
        reference_id=reading.id,
        payload={
            "unit_id": unit_id,
            "recorded_temp_c": temp_c,
            "is_excursion": is_excursion,
            "recorded_by_user_id": recorded_by_user_id,
            "note": note
        }
    )

    if is_excursion:
        event = ColdChainExcursionEvent(
            unit_id=unit_id,
            unit_label=unit.unit_label,
            recorded_temp_c=temp_c,
            min_temp_c=float(unit.min_temp_c),
            max_temp_c=float(unit.max_temp_c),
            reading_id=reading.id,
            db=db
        )
        event_bus.publish(event)

    return reading

def get_readings(db: Session, unit_id: int, hours: int = 24, limit: int = 100) -> List[Dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    readings = db.query(ColdChainReading, User.username).join(
        User, ColdChainReading.recorded_by_user_id == User.id, isouter=True
    ).join(ColdChainUnit, ColdChainReading.unit_id == ColdChainUnit.id).filter(
        ColdChainReading.unit_id == unit_id,
        ColdChainReading.recorded_at >= cutoff
    ).order_by(ColdChainReading.recorded_at.desc()).limit(limit).all()

    result = []
    for r, username in readings:
        result.append({
            "id": r.id,
            "unit_id": r.unit_id,
            "unit_label": r.unit.unit_label,
            "recorded_temp_c": float(r.recorded_temp_c),
            "recorded_by_username": username,
            "recorded_at": r.recorded_at,
            "note": r.note,
            "is_excursion": r.is_excursion
        })
    return result

def get_compliance_report(db: Session, unit_id: Optional[int] = None, days: int = 30) -> Dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    query = db.query(ColdChainReading).filter(ColdChainReading.recorded_at >= cutoff)
    if unit_id is not None:
        query = query.filter(ColdChainReading.unit_id == unit_id)

    readings = query.all()
    total_readings = len(readings)
    excursion_count = sum(1 for r in readings if r.is_excursion)
    compliance_pct = 0.0
    if total_readings > 0:
        compliance_pct = ((total_readings - excursion_count) / total_readings) * 100.0

    # Per-unit breakdown
    units_data = []
    if unit_id is None:
        units = list_units(db, active_only=False)
        for u in units:
            u_readings = [r for r in readings if r.unit_id == u.id]
            u_total = len(u_readings)
            u_exc = sum(1 for r in u_readings if r.is_excursion)
            u_pct = 0.0
            if u_total > 0:
                u_pct = ((u_total - u_exc) / u_total) * 100.0
            units_data.append({
                "unit_id": u.id,
                "unit_label": u.unit_label,
                "total_readings": u_total,
                "excursion_count": u_exc,
                "compliance_pct": u_pct
            })

    # Daily trend
    daily_trend = {}
    for r in readings:
        day_str = r.recorded_at.strftime('%Y-%m-%d')
        if day_str not in daily_trend:
            daily_trend[day_str] = {"total": 0, "excursion": 0}
        daily_trend[day_str]["total"] += 1
        if r.is_excursion:
            daily_trend[day_str]["excursion"] += 1

    trend_list = []
    for d, counts in sorted(daily_trend.items()):
        pct = 0.0
        if counts["total"] > 0:
            pct = ((counts["total"] - counts["excursion"]) / counts["total"]) * 100.0
        trend_list.append({
            "date": d,
            "compliance_pct": pct,
            "total_readings": counts["total"],
            "excursion_count": counts["excursion"]
        })

    return {
        "days": days,
        "total_readings": total_readings,
        "excursion_count": excursion_count,
        "compliance_pct": compliance_pct,
        "units": units_data,
        "daily_trend": trend_list
    }

def get_compromised_batches(db: Session, unit_id: int) -> List[Dict[str, Any]]:
    # A batch is compromised if the unit it's stored in had an excursion.
    # Since small shops typically use one fridge for all cold-chain items,
    # we return all cold-chain batches if this unit had ANY excursion.
    has_excursion = db.query(ColdChainReading).filter_by(unit_id=unit_id, is_excursion=True).first()
    if not has_excursion:
        return []

    batches = db.query(MedicineBatch, Medicine.particulars).join(
        Medicine, MedicineBatch.medicine_id == Medicine.id
    ).filter(
        MedicineBatch.is_cold_chain == True
    ).all()
    
    result = []
    for b, m_name in batches:
        result.append({
            "batch_id": b.id,
            "medicine_id": b.medicine_id,
            "medicine_name": m_name,
            "batch_no": b.batch_no,
            "expiry_date": b.expiry_date,
            "qty_received": float(b.qty_received),
            "is_cold_chain": b.is_cold_chain
        })
    return result

def mark_batch_cold_chain(db: Session, batch_id: int, is_cold_chain: bool = True) -> Optional[MedicineBatch]:
    batch = db.query(MedicineBatch).filter(MedicineBatch.id == batch_id).first()
    if not batch:
        return None
    batch.is_cold_chain = is_cold_chain
    db.commit()
    db.refresh(batch)
    return batch
