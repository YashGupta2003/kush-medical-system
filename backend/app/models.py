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
    Column, Integer, String, Numeric, DateTime, ForeignKey, Text, Enum
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
        Enum("pending_review", "confirmed", "rejected", name="bill_status"),
        default="pending_review",
    )
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    raw_ocr_text = Column(Text)   # full raw OCR dump, kept for debugging / reprocessing

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
        Enum("auto", "manual", "unmatched", "confirmed", name="match_status"),
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
