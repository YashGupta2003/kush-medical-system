from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.services import stock_service, reorder_intelligence
from app.deps import get_current_user

router = APIRouter(prefix="/stock", dependencies=[Depends(get_current_user)],tags=["stock"])


@router.get("/smart-reorder", response_model=list[schemas.SmartThresholdSuggestion])
def get_smart_reorder_list(window_days: int = 30, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return reorder_intelligence.compute_smart_thresholds_bulk(db, window_days=window_days)


@router.get("/medicine/{medicine_id}/smart-threshold", response_model=schemas.SmartThresholdSuggestion)
def get_smart_threshold(medicine_id: int, window_days: int = 30, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    try:
        return reorder_intelligence.compute_smart_threshold(db, medicine_id, window_days=window_days)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/medicine/{medicine_id}/smart-threshold/apply", response_model=schemas.MedicineOut)
def apply_smart_threshold(medicine_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    try:
        return reorder_intelligence.apply_suggested_threshold(db, medicine_id)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.patch("/medicine/{medicine_id}/lead-time", response_model=schemas.MedicineOut)
def update_lead_time(medicine_id: int, payload: schemas.LeadTimeUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    medicine = db.query(models.Medicine).filter_by(id=medicine_id, tenant_id=current_user.tenant_id).first()
    if not medicine:
        raise HTTPException(404, "Medicine not found")
    medicine.lead_time_days = payload.lead_time_days
    db.commit()
    db.refresh(medicine)
    return medicine


@router.get("/medicine/{medicine_id}/snapshot", response_model=schemas.StockSnapshot)
def get_snapshot(medicine_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    snapshot = stock_service.get_stock_snapshot(db, current_user.tenant_id, medicine_id)
    if not snapshot:
        raise HTTPException(404, "Medicine not found")
    return snapshot



@router.post("/sales", response_model=schemas.StockSnapshot)
def record_sale(
    payload: schemas.SaleCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    medicine = db.query(models.Medicine).filter_by(id=payload.medicine_id, tenant_id=current_user.tenant_id).first()
    if not medicine:
        raise HTTPException(404, "Medicine not found")
    try:
        return stock_service.record_sale(
            db, current_user.tenant_id, payload.medicine_id, payload.qty_sold, created_by_user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/reorder-list", response_model=list[schemas.DistributorReorderGroup])
def reorder_list(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return stock_service.get_reorder_list(db, current_user.tenant_id)


@router.post("/reorder-list/manual", response_model=schemas.ReorderMedicineItem)
def add_manual_reorder_item(payload: schemas.ManualReorderCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if not payload.medicine_id and not payload.custom_name:
        raise HTTPException(422, "Provide either medicine_id (existing medicine) or custom_name (new item)")

    item = stock_service.add_manual_reorder_item(
        db,
        medicine_id=payload.medicine_id,
        custom_name=payload.custom_name,
        distributor_id=payload.distributor_id,
        distributor_name_new=payload.distributor_name_new,
        quantity_needed=payload.quantity_needed, tenant_id=current_user.tenant_id,
        note=payload.note,
    )

    name = item.medicine.particulars if item.medicine else (item.custom_name or "Unnamed item")
    return schemas.ReorderMedicineItem(
        id=item.id, medicine_id=item.medicine_id, name=name,
        current_stock=float(item.medicine.current_stock) if item.medicine else None,
        low_stock_threshold=float(item.medicine.low_stock_threshold) if item.medicine and item.medicine.low_stock_threshold is not None else None,
        quantity_needed=float(item.quantity_needed) if item.quantity_needed is not None else None,
        note=item.note, source="manual",
    )


@router.delete("/reorder-list/{reorder_item_id}")
def remove_reorder_item(reorder_item_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    item = db.query(models.ReorderItem).filter_by(id=reorder_item_id, tenant_id=current_user.tenant_id).first()
    if not item: raise HTTPException(404, "Reorder item not found")

    ok = stock_service.delete_reorder_item(db, reorder_item_id)
    if not ok:
        raise HTTPException(404, "Reorder item not found")
    return {"status": "ok"}


@router.patch("/reorder-list/{reorder_item_id}/fulfill")
def fulfill_reorder_item(reorder_item_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    item = db.query(models.ReorderItem).filter_by(id=reorder_item_id, tenant_id=current_user.tenant_id).first()
    if not item: raise HTTPException(404, "Reorder item not found")

    ok = stock_service.mark_reorder_item_fulfilled(db, reorder_item_id)
    if not ok:
        raise HTTPException(404, "Reorder item not found")
    return {"status": "ok"}


@router.get("/ledger")
def get_ledger(limit: int = 50, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return stock_service.get_stock_ledger(db, current_user.tenant_id, limit=limit)


@router.post("/adjustments")
def record_adjustment(
    payload: schemas.StockAdjustmentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    medicine = db.query(models.Medicine).filter_by(id=payload.medicine_id, tenant_id=current_user.tenant_id).first()
    if not medicine:
        raise HTTPException(404, "Medicine not found")
    try:
        return stock_service.record_adjustment(
            db, payload.medicine_id, payload.new_total_stock, payload.note, created_by_user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.patch("/medicine/{medicine_id}/threshold", response_model=schemas.MedicineOut)
def update_threshold(medicine_id: int, payload: schemas.ThresholdUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    medicine = db.query(models.Medicine).filter_by(id=medicine_id, tenant_id=current_user.tenant_id).first()
    if not medicine:
        raise HTTPException(404, "Medicine not found")
    medicine.low_stock_threshold = payload.low_stock_threshold
    db.commit()
    db.refresh(medicine)
    return medicine