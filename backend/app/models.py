"""
Database schema.

medicines      -> the master rate list (replaces your Excel sheet)
distributors   -> Hari Krishna Distributor, Rathore Medicos, Verma Bros, etc.
bills          -> one row per uploaded invoice photo
bill_items     -> one row per line item on a bill (linked to a medicine once matched)
rate_history   -> audit trail: every time a medicine's rate/MRP changes, and why
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Numeric, DateTime,Date, ForeignKey, Text, Enum, Boolean
)
from sqlalchemy.orm import relationship

from app.database import Base


class Medicine(Base):
    __tablename__ = "medicines"

    id = Column(Integer, primary_key=True, index=True)
    particulars = Column(String(255), nullable=False)          # display name, e.g. "AMLOKIND-AT TABS"
    normalized_name = Column(String(255), nullable=False, index=True)  # UPPERCASE, no punctuation - used for matching
    unit = Column(String(50))                                  # pack size, e.g. "1*10", "100 ML"
    mrp = Column(Numeric(10, 2))
    net_rate = Column(Numeric(10, 2))                          # current cost price to the shop
    company = Column(String(100))
    stockist = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    current_stock = Column(Numeric(10, 2), default=0, nullable=False)
    low_stock_threshold = Column(Numeric(10, 2), nullable=True)
    barcode = Column(String(64), nullable=True, unique=True, index=True)

    bill_items = relationship("BillItem", back_populates="medicine")
    rate_history = relationship("RateHistory", back_populates="medicine")


class Distributor(Base):
    __tablename__ = "distributors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False, unique=True)    # e.g. "RATHORE MEDICOS"
    gstin = Column(String(20))
    address = Column(String(255))
    phone = Column(String(50))

    bills = relationship("Bill", back_populates="distributor")


class Bill(Base):
    __tablename__ = "bills"

    id = Column(Integer, primary_key=True, index=True)
    distributor_id = Column(Integer, ForeignKey("distributors.id"), nullable=True)
    invoice_no = Column(String(100))
    invoice_date = Column(DateTime, nullable=True)
    year = Column(Integer, index=True)
    month = Column(Integer, index=True)
    image_path = Column(String(500))
    total_amount = Column(Numeric(10, 2))
    status = Column(
        Enum("queued", "processing", "pending_review", "needs_attention",
             "confirmed", "rejected", "failed", name="bill_status"),
        default="queued",
    )
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    raw_ocr_text = Column(Text)

    celery_task_id = Column(String(100), nullable=True, index=True)
    processing_error = Column(Text, nullable=True)
    ocr_confidence = Column(Numeric(5, 2), nullable=True)
    needs_attention_reason = Column(String(255), nullable=True)
    preprocessing_notes = Column(Text, nullable=True)
    checksum = Column(String(64), nullable=True, index=True)

    # status = Column(
    #     Enum("pending_review", "confirmed", "rejected", name="bill_status"),
    #     default="pending_review",
    # )
    # uploaded_at = Column(DateTime, default=datetime.utcnow)
    # raw_ocr_text = Column(Text)   # full raw OCR dump, kept for debugging / reprocessing

    distributor = relationship("Distributor", back_populates="bills")
    items = relationship("BillItem", back_populates="bill", cascade="all, delete-orphan")


class BillItem(Base):
    __tablename__ = "bill_items"

    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(Integer, ForeignKey("bills.id"), nullable=False)
    medicine_id = Column(Integer, ForeignKey("medicines.id"), nullable=True)  # null until matched

    raw_name = Column(String(255), nullable=False)      # exactly as OCR read it off the bill
    pack = Column(String(50))
    batch = Column(String(50))
    exp_date = Column(String(20))
    qty = Column(Numeric(10, 2), default=0)
    free_qty = Column(Numeric(10, 2), default=0)
    mrp = Column(Numeric(10, 2))
    rate = Column(Numeric(10, 2))                       # printed rate per unit before disc/gst
    discount_pct = Column(Numeric(5, 2), default=0)
    special_discount_pct = Column(Numeric(5, 2), default=0)   # 2nd/flat discount, if any
    gst_pct = Column(Numeric(5, 2), default=0)
    amount = Column(Numeric(10, 2))                     # printed line amount, for cross-check

    computed_cost_per_unit = Column(Numeric(10, 2))     # <-- the number that updates medicines.net_rate

    match_confidence = Column(Numeric(5, 2))            # 0-100 fuzzy match score
    match_status = Column(
        Enum("auto", "learned", "manual", "unmatched", "confirmed", name="match_status"),
        default="unmatched",
    )
    bill = relationship("Bill", back_populates="items")
    medicine = relationship("Medicine", back_populates="bill_items")


class RateHistory(Base):
    __tablename__ = "rate_history"

    id = Column(Integer, primary_key=True, index=True)
    medicine_id = Column(Integer, ForeignKey("medicines.id"), nullable=False)
    bill_item_id = Column(Integer, ForeignKey("bill_items.id"), nullable=True)

    old_net_rate = Column(Numeric(10, 2))
    new_net_rate = Column(Numeric(10, 2))
    old_mrp = Column(Numeric(10, 2))
    new_mrp = Column(Numeric(10, 2))
    changed_at = Column(DateTime, default=datetime.utcnow)

    medicine = relationship("Medicine", back_populates="rate_history")

class UserMapping(Base):
    """
    The 'learning' table. Every time a user manually picks or corrects which
    medicine a bill line item actually is, that choice is remembered here.
    """
    __tablename__ = "user_mappings"

    id = Column(Integer, primary_key=True, index=True)
    distributor_id = Column(Integer, ForeignKey("distributors.id"), nullable=True, index=True)
    raw_name = Column(String(255), nullable=False, index=True)
    medicine_id = Column(Integer, ForeignKey("medicines.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    medicine = relationship("Medicine")
    distributor = relationship("Distributor")

class Sale(Base):
    __tablename__ = "sales"

    id = Column(Integer, primary_key=True, index=True)
    medicine_id = Column(Integer, ForeignKey("medicines.id"), nullable=False, index=True)
    qty_sold = Column(Numeric(10, 2), nullable=False)
    sold_at = Column(DateTime, default=datetime.utcnow)

    medicine = relationship("Medicine")


class StockLedger(Base):
    __tablename__ = "stock_ledger"

    id = Column(Integer, primary_key=True, index=True)
    medicine_id = Column(Integer, ForeignKey("medicines.id"), nullable=False, index=True)
    change_qty = Column(Numeric(10, 2), nullable=False)
    resulting_balance = Column(Numeric(10, 2), nullable=False)
    reason = Column(Enum("bill_received", "sale", "manual_adjustment", name="stock_reason"), nullable=False)
    reference_bill_item_id = Column(Integer, ForeignKey("bill_items.id"), nullable=True)
    reference_sale_id = Column(Integer, ForeignKey("sales.id"), nullable=True)
    note = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    medicine = relationship("Medicine")


class ReorderItem(Base):
    __tablename__ = "reorder_items"

    id = Column(Integer, primary_key=True, index=True)
    medicine_id = Column(Integer, ForeignKey("medicines.id"), nullable=True)
    custom_name = Column(String(255), nullable=True)
    distributor_id = Column(Integer, ForeignKey("distributors.id"), nullable=True)
    quantity_needed = Column(Numeric(10, 2), nullable=True)
    note = Column(String(255), nullable=True)
    source = Column(Enum("auto_low_stock", "manual", name="reorder_source"), default="manual")
    fulfilled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    medicine = relationship("Medicine")
    distributor = relationship("Distributor")

class MedicineBatch(Base):
    __tablename__ = "medicine_batches"

    id = Column(Integer, primary_key=True, index=True)
    medicine_id = Column(Integer, ForeignKey("medicines.id"), nullable=False, index=True)
    batch_no = Column(String(50), nullable=True)
    expiry_date = Column(Date, nullable=True, index=True)
    qty_received = Column(Numeric(10, 2), nullable=False, default=0)
    bill_item_id = Column(Integer, ForeignKey("bill_items.id"), nullable=True, unique=True)
    distributor_id = Column(Integer, ForeignKey("distributors.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    medicine = relationship("Medicine")
    distributor = relationship("Distributor")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=True)
    role = Column(Enum("owner", "staff", name="user_role"), nullable=False, default="staff")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)