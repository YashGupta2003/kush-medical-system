"""
Database schema.

medicines      -> the master rate list (replaces your Excel sheet)
distributors   -> Hari Krishna Distributor, Rathore Medicos, Verma Bros, etc.
bills          -> one row per uploaded invoice photo
bill_items     -> one row per line item on a bill (linked to a medicine once matched)
rate_history   -> audit trail: every time a medicine's rate/MRP changes, and why
"""
from datetime import datetime, timezone
from sqlalchemy import (
    UniqueConstraint,
    Column, Integer, String, Numeric, DateTime, Date, ForeignKey, Text, Enum, Boolean, func
)
from sqlalchemy.orm import relationship

from app.database import Base



class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(80), nullable=False, unique=True, index=True)
    shop_name = Column(String(150), nullable=False)
    owner_name = Column(String(150), nullable=False)
    email = Column(String(150), nullable=False, unique=True, index=True)
    phone = Column(String(20), nullable=True)
    gstin = Column(String(20), nullable=True)
    city = Column(String(100), nullable=True)
    address = Column(Text, nullable=True)
    plan = Column(String(50), default="free")
    is_active = Column(Boolean, default=True, nullable=False)
    email_verified = Column(Boolean, default=False)
    email_verification_token = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    # Regional Health Sentinel (migration 0023): opt-in regional surveillance
    region_code = Column(String(50), nullable=True)
    surveillance_opt_in = Column(Boolean, nullable=False, default=False, server_default="0")

    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")

class Medicine(Base):
    __tablename__ = "medicines"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    particulars = Column(String(255), nullable=False)          # display name, e.g. "AMLOKIND-AT TABS"
    normalized_name = Column(String(255), nullable=False, index=True)  # UPPERCASE, no punctuation - used for matching
    unit = Column(String(50))                                  # pack size, e.g. "1*10", "100 ML"
    mrp = Column(Numeric(10, 2))
    net_rate = Column(Numeric(10, 2))                          # current cost price to the shop
    company = Column(String(100))
    stockist = Column(String(100))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

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
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    name = Column(String(150), nullable=False, unique=True)    # e.g. "RATHORE MEDICOS"
    gstin = Column(String(20))
    address = Column(String(255))
    phone = Column(String(50))

    bills = relationship("Bill", back_populates="distributor")


class Bill(Base):
    __tablename__ = "bills"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
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
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    raw_ocr_text = Column(Text)

    celery_task_id = Column(String(100), nullable=True, index=True)
    processing_error = Column(Text, nullable=True)
    ocr_confidence = Column(Numeric(5, 2), nullable=True)
    needs_attention_reason = Column(String(255), nullable=True)
    preprocessing_notes = Column(Text, nullable=True)
    checksum = Column(String(64), nullable=True, index=True)

    distributor = relationship("Distributor", back_populates="bills")
    items = relationship("BillItem", back_populates="bill", cascade="all, delete-orphan")


class BillItem(Base):
    __tablename__ = "bill_items"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
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
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    medicine_id = Column(Integer, ForeignKey("medicines.id"), nullable=False)
    bill_item_id = Column(Integer, ForeignKey("bill_items.id"), nullable=True)

    old_net_rate = Column(Numeric(10, 2))
    new_net_rate = Column(Numeric(10, 2))
    old_mrp = Column(Numeric(10, 2))
    new_mrp = Column(Numeric(10, 2))
    changed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    medicine = relationship("Medicine", back_populates="rate_history")

class UserMapping(Base):
    """
    The 'learning' table. Every time a user manually picks or corrects which
    medicine a bill line item actually is, that choice is remembered here.
    """
    __tablename__ = "user_mappings"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    distributor_id = Column(Integer, ForeignKey("distributors.id"), nullable=True, index=True)
    raw_name = Column(String(255), nullable=False, index=True)
    medicine_id = Column(Integer, ForeignKey("medicines.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    medicine = relationship("Medicine")
    distributor = relationship("Distributor")

class Sale(Base):
    __tablename__ = "sales"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    medicine_id = Column(Integer, ForeignKey("medicines.id"), nullable=False, index=True)
    qty_sold = Column(Numeric(10, 2), nullable=False)
    sold_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)   # NEW (Pillar 5)

    medicine = relationship("Medicine")
    customer = relationship("Customer", back_populates="sales")


class StockLedger(Base):
    __tablename__ = "stock_ledger"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    medicine_id = Column(Integer, ForeignKey("medicines.id"), nullable=False, index=True)
    change_qty = Column(Numeric(10, 2), nullable=False)
    resulting_balance = Column(Numeric(10, 2), nullable=False)
    reason = Column(Enum("bill_received", "sale", "manual_adjustment", name="stock_reason"), nullable=False)
    reference_bill_item_id = Column(Integer, ForeignKey("bill_items.id"), nullable=True)
    reference_sale_id = Column(Integer, ForeignKey("sales.id"), nullable=True)
    note = Column(String(255), nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)   # NEW (Pillar 6)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    medicine = relationship("Medicine")
    created_by = relationship("User")


class ReorderItem(Base):
    __tablename__ = "reorder_items"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    medicine_id = Column(Integer, ForeignKey("medicines.id"), nullable=True)
    custom_name = Column(String(255), nullable=True)
    distributor_id = Column(Integer, ForeignKey("distributors.id"), nullable=True)
    quantity_needed = Column(Numeric(10, 2), nullable=True)
    note = Column(String(255), nullable=True)
    source = Column(Enum("auto_low_stock", "manual", name="reorder_source"), default="manual")
    fulfilled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    medicine = relationship("Medicine")
    distributor = relationship("Distributor")

class MedicineBatch(Base):
    __tablename__ = "medicine_batches"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    medicine_id = Column(Integer, ForeignKey("medicines.id"), nullable=False, index=True)
    batch_no = Column(String(50), nullable=True)
    expiry_date = Column(Date, nullable=True, index=True)
    qty_received = Column(Numeric(10, 2), nullable=False, default=0)
    bill_item_id = Column(Integer, ForeignKey("bill_items.id"), nullable=True, unique=True)
    distributor_id = Column(Integer, ForeignKey("distributors.id"), nullable=True)
    is_cold_chain = Column(Boolean, nullable=True, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    medicine = relationship("Medicine")
    distributor = relationship("Distributor")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    username = Column(String(50), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=True)
    role = Column(Enum("owner", "staff", name="user_role"), nullable=False, default="staff")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    # Priority 1: WhatsApp delivery column (migration 0013)
    whatsapp_number = Column(String(20), nullable=True)

    @property
    def shop_name(self):
        return self.tenant.shop_name if self.tenant else None

    tenant = relationship("Tenant", back_populates="users")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", foreign_keys="[Notification.recipient_user_id]",
                                 back_populates="recipient_user", cascade="all, delete-orphan")


class RefreshToken(Base):
    """
    Priority 2a — Refresh token flow.

    Stores the SHA-256 hash of the refresh token (never the raw token),
    similar to how password hashes work. The raw UUID4 token is returned
    to the client on login and never stored here.

    Revocation is done by setting `revoked=True` — a hard delete would also
    work, but soft-deletion gives an audit trail of "this token was revoked
    at this time," which is useful if you ever investigate a session hijack
    incident.
    """
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="refresh_tokens")


class MedicineSalt(Base):
    """
    One row per individual salt inside a medicine's composition, produced by
    composition_service.parse_composition(). A combination drug like
    "Paracetamol 650mg + Caffeine 30mg" gets TWO rows here.
    """
    __tablename__ = "medicine_salts"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
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
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    source_type = Column(String(30), nullable=False, index=True)
    source_id = Column(String(150), nullable=False, index=True)
    edge_type = Column(String(30), nullable=False, index=True)
    target_type = Column(String(30), nullable=False)
    target_id = Column(String(150), nullable=False, index=True)
    weight = Column(Numeric(5, 2), nullable=True)
    edge_metadata = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

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
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    event_type = Column(String(50), nullable=False, index=True)   # "rate_change" | "batch_received" | "bill_confirmed" | "stock_adjustment"
    reference_id = Column(Integer, nullable=True, index=True)      # e.g. RateHistory.id, MedicineBatch.id, Bill.id, StockLedger.id

    payload_json = Column(Text, nullable=False)     # canonical JSON of the event's actual data
    payload_hash = Column(String(64), nullable=False)   # SHA-256(payload_json)
    previous_hash = Column(String(64), nullable=False)  # chains to the prior ledger entry's entry_hash
    entry_hash = Column(String(64), nullable=False, unique=True, index=True)  # SHA-256(payload_hash + previous_hash)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

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
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    phone = Column(String(15), nullable=False, unique=True, index=True)
    name = Column(String(100), nullable=True)
    consent_given_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

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
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    change_amount = Column(Numeric(10, 2), nullable=False)   # positive = customer now owes more, negative = payment reduces balance
    resulting_balance = Column(Numeric(10, 2), nullable=False)
    reason = Column(Enum("credit_sale", "payment_received", "adjustment", name="credit_reason"), nullable=False)
    reference_sale_id = Column(Integer, ForeignKey("sales.id"), nullable=True)
    note = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

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
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    shop_name = Column(String(150), nullable=False)
    api_base_url = Column(String(255), nullable=True)   # where a real deployment would sync to
    contact_phone = Column(String(50), nullable=True)
    is_self = Column(Boolean, default=False)
    opted_in = Column(Boolean, default=True)
    joined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


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
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
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
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    pharmacy_node = relationship("PharmacyNode", foreign_keys=[pharmacy_node_id])
    claimed_by_node = relationship("PharmacyNode", foreign_keys=[claimed_by_node_id])


class Notification(Base):
    """
    Priority 1 — Notification Engine.

    The proactive alerting table — every pillar's signals (adherence
    overdue, anomaly flags, low-stock crossings, credit overdue, near-expiry,
    TrustChain tamper) land here as rows so the owner sees them without
    opening six tabs.

    Design decisions documented in app/services/notification_service.py.
    Single write path: notification_service.create_notification() only.

    related_entity_type / related_entity_id use the same "loose reference"
    pattern as AuditLedgerEntry's event_type/reference_id — avoids N
    foreign key constraints for a table that can reference a dozen different
    entity types across all pillars.
    """
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    recipient_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    notification_type = Column(
        Enum(
            "adherence_overdue", "anomaly_flagged", "low_stock_crossed",
            "credit_overdue", "trust_chain_tamper", "near_expiry",
            "daily_digest", "system", "cross_tenant_alert", "regional_health_spike",
            name="notification_type",
        ),
        nullable=False,
        index=True,
    )
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    severity = Column(
        Enum("info", "warning", "critical", name="notification_severity"),
        nullable=False,
        default="info",
    )
    related_entity_type = Column(String(50), nullable=True)
    related_entity_id = Column(String(50), nullable=True)
    channel = Column(
        Enum("in_app", "whatsapp", "sms", "email", name="notification_channel"),
        nullable=False,
        default="in_app",
    )
    is_read = Column(Boolean, nullable=False, default=False)
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    recipient_user = relationship("User", foreign_keys=[recipient_user_id],
                                  back_populates="notifications")
class SurveillanceDailyCount(Base):
    """
    Syndromic Surveillance — privacy-safe daily aggregated counts.

    Records HOW MANY OTC units were sold for each health condition on each
    date — never which customer, which specific medicine, or which sale.
    This is the Privacy-by-Construction guarantee: row-level patient/sale
    data never crosses the network boundary; only pre-aggregated daily
    counts per condition exist in this table.

    Integrates with Pillar 1 (PharmaGraph's TREATS edges map medicines
    to conditions) and Pillar 6 (anomaly_service._leave_one_out_zscores
    detects spikes in the daily count time series).
    """
    __tablename__ = "surveillance_daily_counts"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    condition_name = Column(String(150), nullable=False, index=True)
    count_date = Column(Date, nullable=False, index=True)
    otc_units = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint('tenant_id', 'condition_name', 'count_date', name='uq_surveillance_daily_counts_tenant_cond_date'),
    )

class ColdChainUnit(Base):
    """
    Cold-Chain Compliance Ledger — a single refrigeration/cold-storage unit.

    Each pharmacy may have 1-3 fridges storing temperature-sensitive items
    (vaccines, insulin, certain eye drops). The min_temp_c/max_temp_c range
    defines the acceptable operating window — readings outside this range
    are flagged as excursions.

    Design decision: temperature ranges are per-unit, not per-medicine,
    because in practice a small shop puts all cold-chain items in the same
    fridge and the compliance question is "was the fridge in range" not
    "was each individual medicine at the right temp."
    """
    __tablename__ = "cold_chain_units"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    unit_label = Column(String(100), nullable=False, unique=True)
    location_note = Column(String(255), nullable=True)
    min_temp_c = Column(Numeric(5, 2), nullable=False, default=2.0)
    max_temp_c = Column(Numeric(5, 2), nullable=False, default=8.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    readings = relationship("ColdChainReading", back_populates="unit", cascade="all, delete-orphan")


class ColdChainReading(Base):
    """
    Cold-Chain Compliance Ledger — one temperature reading for a unit.

    Logged by staff (recorded_by_user_id) at regular intervals. The
    is_excursion flag is computed at write time based on whether
    recorded_temp_c falls outside the unit's [min_temp_c, max_temp_c] range.

    Every reading is ALSO logged to TrustChain (Pillar 4) via
    audit_service.log_event — temperature compliance is a regulatory
    requirement where tamper-evidence matters (an inspector asking "were
    your vaccines stored correctly" needs an audit trail that can't be
    quietly edited after the fact).
    """
    __tablename__ = "cold_chain_readings"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    unit_id = Column(Integer, ForeignKey("cold_chain_units.id"), nullable=False, index=True)
    recorded_temp_c = Column(Numeric(5, 2), nullable=False)
    recorded_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    recorded_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    note = Column(String(255), nullable=True)
    is_excursion = Column(Boolean, nullable=False, default=False)

    unit = relationship("ColdChainUnit", back_populates="readings")
    recorded_by = relationship("User")


class DistributorTrustScore(Base):
    """
    Feature 4 — Supply Chain Trust Score cache.

    Stores the last-computed composite trust score for each distributor,
    enabling efficient threshold-crossing detection ("is this score newly
    below HIGH_RISK_THRESHOLD?") without recomputing from scratch on
    every request. Upserted by trust_score_service.compute_trust_score.
    """
    __tablename__ = "distributor_trust_scores"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    distributor_id = Column(Integer, ForeignKey("distributors.id"), nullable=False, index=True)
    medicine_id = Column(Integer, ForeignKey("medicines.id"), nullable=True, index=True)
    score = Column(Numeric(5, 2), nullable=False)
    confidence = Column(String(20), nullable=False)
    computed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    distributor = relationship("Distributor")

    __table_args__ = (
        UniqueConstraint('distributor_id', 'medicine_id', name='uq_distributor_trust_score'),
    )


class Prescription(Base):
    """
    Prescription Intelligence Engine (PIE) — one row per scanned prescription.

    Links OCR → PharmaGraph → Customer → POS in a single document:
    - image_path: saved prescription photo
    - customer_id: optional, linked by phone at scan time
    - status: queued → processing → ready → converted / abandoned
    - converted_to_sale: True once a POS cart sale was recorded from this prescription
    - purchased_at: timestamp of the POS sale (to compute 'uncollected' after 30 min)
    - raw_ocr_text: full OCR dump for debugging
    - doctor_name / clinic_name: extracted from OCR header, nullable
    """
    __tablename__ = "prescriptions"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)
    image_path = Column(String(500), nullable=False)
    status = Column(
        Enum("queued", "processing", "ready", "converted", "abandoned", name="prescription_status"),
        default="queued", nullable=False, index=True
    )
    converted_to_sale = Column(Boolean, default=False, nullable=False)
    purchased_at = Column(DateTime, nullable=True)
    raw_ocr_text = Column(Text, nullable=True)
    ocr_confidence = Column(Numeric(5, 2), nullable=True)
    doctor_name = Column(String(150), nullable=True)
    clinic_name = Column(String(200), nullable=True)
    processing_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    customer = relationship("Customer")
    items = relationship("PrescriptionItem", back_populates="prescription", cascade="all, delete-orphan")


class PrescriptionItem(Base):
    """
    One drug line on a scanned prescription.

    - raw_name: exactly as OCR read it
    - medicine_id: resolved by fuzzy matcher (nullable until matched)
    - match_confidence / match_status: same semantics as BillItem
    - qty_prescribed: dosage quantity extracted from prescription
    - in_stock: snapshot at scan time (True/False)
    - substitute_medicine_id: if OOS, the best in-stock substitute found by composition_service
    - added_to_cart: True once the pharmacist added this line to a POS cart
    """
    __tablename__ = "prescription_items"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    prescription_id = Column(Integer, ForeignKey("prescriptions.id"), nullable=False, index=True)
    medicine_id = Column(Integer, ForeignKey("medicines.id"), nullable=True, index=True)
    substitute_medicine_id = Column(Integer, ForeignKey("medicines.id"), nullable=True)

    raw_name = Column(String(255), nullable=False)
    qty_prescribed = Column(Numeric(10, 2), nullable=True)
    dosage_instructions = Column(String(255), nullable=True)
    match_confidence = Column(Numeric(5, 2), nullable=True)
    match_status = Column(
        Enum("auto", "learned", "manual", "unmatched", name="rx_match_status"),
        default="unmatched"
    )
    in_stock = Column(Boolean, nullable=True)
    current_stock_qty = Column(Numeric(10, 2), nullable=True)
    added_to_cart = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    prescription = relationship("Prescription", back_populates="items")
    medicine = relationship("Medicine", foreign_keys=[medicine_id])
    substitute_medicine = relationship("Medicine", foreign_keys=[substitute_medicine_id])

class CrossTenantBatchAlert(Base):
    __tablename__ = "cross_tenant_batch_alerts"

    id = Column(Integer, primary_key=True, index=True)
    medicine_name = Column(String(255), nullable=False)
    normalized_batch_no = Column(String(100), nullable=False, index=True)
    tenant_ids = Column(Text, nullable=False)
    distributor_names = Column(Text, nullable=False)
    occurrence_count = Column(Integer, nullable=False, default=0)
    first_seen = Column(DateTime, nullable=True)
    last_seen = Column(DateTime, nullable=True)
    status = Column(Enum("open", "reviewed", "dismissed", name="cross_tenant_alert_status"), nullable=False, server_default="open")
    severity = Column(Enum("medium", "high", name="cross_tenant_alert_severity"), nullable=False, server_default="high")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("normalized_batch_no", "medicine_name", name="uix_batch_medicine"),
    )


class RegionalHealthAlert(Base):
    """
    Regional Health Sentinel — one alert row per (region_code, condition_name, alert_date) triple.

    Written exclusively by regional_health_service.scan_regional_spikes().
    Read by get_alerts_for_tenant(), which deliberately omits region_code and
    any other-tenant-identifying fields from its return value — only the
    combined aggregate stats are exposed to the requesting tenant.
    """
    __tablename__ = "regional_health_alerts"

    id = Column(Integer, primary_key=True, index=True)
    region_code = Column(String(50), nullable=False, index=True)
    condition_name = Column(String(150), nullable=False)
    alert_date = Column(Date, nullable=False)
    contributing_tenant_count = Column(Integer, nullable=False)
    total_regional_units = Column(Integer, nullable=False)
    regional_avg_units = Column(Numeric(10, 2), nullable=False)
    z_score = Column(Numeric(6, 3), nullable=False)
    severity = Column(
        Enum("watch", "elevated", "critical", name="regional_alert_severity"),
        nullable=False,
        server_default="watch",
    )
    status = Column(
        Enum("open", "acknowledged", "dismissed", name="regional_alert_status"),
        nullable=False,
        server_default="open",
    )
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("region_code", "condition_name", "alert_date", name="uix_regional_alert_region_cond_date"),
    )
