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

    # --- Substitute Medicine Suggestion feature ---
    composition = Column(String(500), nullable=True)   # raw display text, e.g. "Paracetamol 650mg"


    lead_time_days = Column(Integer, nullable=True)
    suggested_low_stock_threshold = Column(Numeric(10, 2), nullable=True)
    avg_daily_sales_30d = Column(Numeric(10, 2), nullable=True)
    suggestion_computed_at = Column(DateTime, nullable=True)

    bill_items = relationship("BillItem", back_populates="medicine")
    rate_history = relationship("RateHistory", back_populates="medicine")
    salts = relationship("MedicineSalt", back_populates="medicine", cascade="all, delete-orphan")


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
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)   # NEW (Pillar 5)
 
    medicine = relationship("Medicine")
    customer = relationship("Customer", back_populates="sales") 


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

class MedicineSalt(Base):
    """
    One row per individual salt inside a medicine's composition, produced by
    composition_service.parse_composition(). A combination drug like
    "Paracetamol 650mg + Caffeine 30mg" gets TWO rows here.
    """
    __tablename__ = "medicine_salts"

    id = Column(Integer, primary_key=True, index=True)
    medicine_id = Column(Integer, ForeignKey("medicines.id"), nullable=False, index=True)
    salt_name = Column(String(150), nullable=False, index=True)
    strength = Column(String(50), nullable=True)

    medicine = relationship("Medicine", back_populates="salts")


class GraphEdge(Base):
    """
    PharmaGraph - a generic typed-edge table implementing a knowledge graph
    on top of the existing relational schema.
    """
    __tablename__ = "graph_edges"

    id = Column(Integer, primary_key=True, index=True)
    source_type = Column(String(30), nullable=False, index=True)
    source_id = Column(String(150), nullable=False, index=True)
    edge_type = Column(String(30), nullable=False, index=True)
    target_type = Column(String(30), nullable=False)
    target_id = Column(String(150), nullable=False, index=True)
    weight = Column(Numeric(5, 2), nullable=True)
    edge_metadata = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AuditLedgerEntry(Base):
    """
    TrustChain — Pillar 4's tamper-evident audit trail.
 
    This is a HASH CHAIN, not a blockchain, and that's a deliberate,
    documented engineering decision (see app/services/audit_service.py for
    the full reasoning): a single shop's database has ONE trust boundary
    (you trust your own MySQL instance), so a distributed ledger would be
    solving a problem this system doesn't have. What a hash chain gives
    you for 1% of the complexity is the property that actually matters —
    TAMPER-EVIDENCE: if anyone (even someone with direct DB access) edits
    a past entry, every entry chained after it visibly breaks.
 
    Every other service/router that wants to write an audit entry goes
    through app/services/audit_service.py's log_event() — never inserts
    into this table directly, matching this codebase's existing
    single-writer convention (see graph_service.py for graph_edges).
    """
    __tablename__ = "audit_ledger"
 
    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(50), nullable=False, index=True)   # "rate_change" | "batch_received" | "bill_confirmed" | "stock_adjustment"
    reference_id = Column(Integer, nullable=True, index=True)      # e.g. RateHistory.id, MedicineBatch.id, Bill.id, StockLedger.id
 
    payload_json = Column(Text, nullable=False)     # canonical JSON of the event's actual data
    payload_hash = Column(String(64), nullable=False)   # SHA-256(payload_json)
    previous_hash = Column(String(64), nullable=False)  # chains to the prior ledger entry's entry_hash
    entry_hash = Column(String(64), nullable=False, unique=True, index=True)  # SHA-256(payload_hash + previous_hash)
 
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

class Customer(Base):
    """
    Pillar 5, Part A — the single new model that powers three features:
    the credit/udhaar ledger, adherence (refill-overdue) tracking, and the
    symptom-to-stock bot's identity. Identified by phone number, the
    natural ID a small shop already uses.
 
    consent_given_at is deliberately separate from "customer exists" - a
    customer can be in the credit ledger (a factual debt record) without
    having opted into their purchase PATTERN being used for adherence
    tracking. See app/services/customer_service.py's module docstring.
    """
    __tablename__ = "customers"
 
    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(15), nullable=False, unique=True, index=True)
    name = Column(String(100), nullable=True)
    consent_given_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
 
    credit_entries = relationship("CustomerCredit", back_populates="customer", cascade="all, delete-orphan")
    sales = relationship("Sale", back_populates="customer")
 
 
class CustomerCredit(Base):
    """
    The credit/udhaar running ledger - same "every change is one immutable
    row, balance is derived by walking forward from the last row" design
    already used by StockLedger (see stock_service.py's _add_ledger_entry).
    Every charge/payment is ALSO logged to TrustChain (Pillar 4) via
    audit_service.log_event - see customer_service.py's charge_credit()
    and record_payment().
    """
    __tablename__ = "customer_credit_ledger"
 
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    change_amount = Column(Numeric(10, 2), nullable=False)   # positive = customer now owes more, negative = payment reduces balance
    resulting_balance = Column(Numeric(10, 2), nullable=False)
    reason = Column(Enum("credit_sale", "payment_received", "adjustment", name="credit_reason"), nullable=False)
    reference_sale_id = Column(Integer, ForeignKey("sales.id"), nullable=True)
    note = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
 
    customer = relationship("Customer", back_populates="credit_entries")
 
 
class PharmacyNode(Base):
    """
    Pillar 5, Part B — one participating pharmacy in the inter-pharmacy
    network. is_self=True marks the row representing THIS shop's own
    instance (auto-created on first use - see network_service.
    get_or_create_self_node). Every other row represents a nearby
    participating pharmacy - see network_service.py's module docstring
    for the honest scoping note on how this models multi-shop
    participation within a single project's single database.
    """
    __tablename__ = "pharmacy_nodes"
 
    id = Column(Integer, primary_key=True, index=True)
    shop_name = Column(String(150), nullable=False)
    api_base_url = Column(String(255), nullable=True)   # where a real deployment would sync to
    contact_phone = Column(String(50), nullable=True)
    is_self = Column(Boolean, default=False)
    opted_in = Column(Boolean, default=True)
    joined_at = Column(DateTime, default=datetime.utcnow)
 
 
class NetworkListing(Base):
    """
    A near-expiry / excess-stock / shortage-request post on the network.
    Claiming a listing posted by a DIFFERENT node, and fulfilling it, both
    log tamper-evident entries to TrustChain (Pillar 4) - a transfer
    between two independent pharmacy owners is exactly the multi-party
    trust scenario that justifies TrustChain's framing (see
    network_service.py's claim_listing / fulfill_listing).
    """
    __tablename__ = "network_listings"
 
    id = Column(Integer, primary_key=True, index=True)
    pharmacy_node_id = Column(Integer, ForeignKey("pharmacy_nodes.id"), nullable=False, index=True)
    listing_type = Column(Enum("near_expiry", "excess_stock", "shortage_request", name="listing_type"), nullable=False, index=True)
    medicine_name = Column(String(255), nullable=False)
    composition = Column(String(500), nullable=True)
    quantity = Column(Numeric(10, 2), nullable=True)
    expiry_date = Column(Date, nullable=True)
    note = Column(String(255), nullable=True)
    status = Column(Enum("open", "claimed", "fulfilled", "withdrawn", name="listing_status"), nullable=False, default="open", index=True)
    claimed_by_node_id = Column(Integer, ForeignKey("pharmacy_nodes.id"), nullable=True)
    source_batch_id = Column(Integer, ForeignKey("medicine_batches.id"), nullable=True)   # links auto-published near_expiry listings back to their batch, for idempotent re-publishing
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
 
    pharmacy_node = relationship("PharmacyNode", foreign_keys=[pharmacy_node_id])
    claimed_by_node = relationship("PharmacyNode", foreign_keys=[claimed_by_node_id])
 