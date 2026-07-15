from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class MedicineOut(BaseModel):
    id: int
    particulars: str
    unit: Optional[str]
    mrp: Optional[float]
    net_rate: Optional[float]
    company: Optional[str]
    stockist: Optional[str]

    class Config:
        from_attributes = True


class RateHistoryOut(BaseModel):
    id: int
    old_net_rate: Optional[float]
    new_net_rate: Optional[float]
    old_mrp: Optional[float]
    new_mrp: Optional[float]
    changed_at: datetime

    class Config:
        from_attributes = True


class BillItemOut(BaseModel):
    id: int
    raw_name: str
    pack: Optional[str]
    batch: Optional[str]
    exp_date: Optional[str]
    qty: Optional[float]
    free_qty: Optional[float]
    mrp: Optional[float]
    rate: Optional[float]
    discount_pct: Optional[float]
    special_discount_pct: Optional[float]
    gst_pct: Optional[float]
    amount: Optional[float]
    computed_cost_per_unit: Optional[float]
    match_confidence: Optional[float]
    match_status: str
    medicine_id: Optional[int]
    suggested_medicine_name: Optional[str] = None  # filled in by the matcher for display

    class Config:
        from_attributes = True


class BillItemEdit(BaseModel):
    """Sent back by the frontend after the user reviews/edits a staged item."""
    id: int
    raw_name: Optional[str] = None
    qty: Optional[float] = None
    free_qty: Optional[float] = None
    mrp: Optional[float] = None
    rate: Optional[float] = None
    discount_pct: Optional[float] = None
    special_discount_pct: Optional[float] = None
    gst_pct: Optional[float] = None
    medicine_id: Optional[int] = None       # user can manually pick the correct medicine
    apply_to_master_list: bool = True       # user can uncheck to skip updating master rate for this item


class BillOut(BaseModel):
    id: int
    distributor_name: Optional[str] = None
    invoice_no: Optional[str]
    invoice_date: Optional[datetime]
    year: Optional[int]
    month: Optional[int]
    total_amount: Optional[float]
    status: str
    uploaded_at: datetime
    items: List[BillItemOut] = []

    class Config:
        from_attributes = True


class ConfirmBillRequest(BaseModel):
    bill_id: int
    items: List[BillItemEdit]


class ChangeSummaryItem(BaseModel):
    medicine_name: str
    field: str            # "net_rate" or "mrp"
    old_value: Optional[float]
    new_value: Optional[float]
