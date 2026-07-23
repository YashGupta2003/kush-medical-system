from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.services import stock_service

router = APIRouter(prefix="/stock", tags=["stock"])


@router.get("/medicine/{medicine_id}/snapshot", response_model=schemas.StockSnapshot)
def get_snapshot(medicine_id: int, db: Session = Depends(get_db)):
    snapshot = stock_service.get_stock_snapshot(db, medicine_id)
    if not snapshot:
        raise HTTPException(404, "Medicine not found")
    return snapshot


@router.post("/sales", response_model=schemas.StockSnapshot)
def record_sale(payload: schemas.SaleCreate, db: Session = Depends(get_db)):
    medicine = db.query(models.Medicine).get(payload.medicine_id)
    if not medicine:
        raise HTTPException(404, "Medicine not found")
    try:
        return stock_service.record_sale(db, payload.medicine_id, payload.qty_sold)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/reorder-list", response_model=list[schemas.DistributorReorderGroup])
def reorder_list(db: Session = Depends(get_db)):
    return stock_service.get_reorder_list(db)


@router.post("/reorder-list/manual", response_model=schemas.ReorderMedicineItem)
def add_manual_reorder_item(payload: schemas.ManualReorderCreate, db: Session = Depends(get_db)):
    if not payload.medicine_id and not payload.custom_name:
        raise HTTPException(422, "Provide either medicine_id (existing medicine) or custom_name (new item)")

    item = stock_service.add_manual_reorder_item(
        db,
        medicine_id=payload.medicine_id,
        custom_name=payload.custom_name,
        distributor_id=payload.distributor_id,
        distributor_name_new=payload.distributor_name_new,
        quantity_needed=payload.quantity_needed,
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
def remove_reorder_item(reorder_item_id: int, db: Session = Depends(get_db)):
    ok = stock_service.mark_reorder_item_fulfilled(db, reorder_item_id)
    if not ok:
        raise HTTPException(404, "Reorder item not found")
    return {"status": "ok"}


@router.patch("/medicine/{medicine_id}/threshold", response_model=schemas.MedicineOut)
def update_threshold(medicine_id: int, payload: schemas.ThresholdUpdate, db: Session = Depends(get_db)):
    medicine = db.query(models.Medicine).get(medicine_id)
    if not medicine:
        raise HTTPException(404, "Medicine not found")
    medicine.low_stock_threshold = payload.low_stock_threshold
    db.commit()
    db.refresh(medicine)
    return medicine
