from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, ConfigDict


class MedicineOut(BaseModel):
    id: int
    particulars: str
    unit: Optional[str] = None
    mrp: Optional[float] = None
    net_rate: Optional[float] = None
    company: Optional[str] = None
    stockist: Optional[str] = None
    current_stock: Optional[float] = None
    low_stock_threshold: Optional[float] = None
    barcode: Optional[str] = None
    composition: Optional[str] = None
    lead_time_days: Optional[int] = None
    suggested_low_stock_threshold: Optional[float] = None
    avg_daily_sales_30d: Optional[float] = None
    suggestion_computed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedMedicines(BaseModel):
    items: List[MedicineOut]
    total: int
    page: int
    page_size: int


class RateHistoryOut(BaseModel):
    id: int
    old_net_rate: Optional[float] = None
    new_net_rate: Optional[float] = None
    old_mrp: Optional[float] = None
    new_mrp: Optional[float] = None
    changed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BillItemOut(BaseModel):
    id: int
    raw_name: str
    pack: Optional[str] = None
    batch: Optional[str] = None
    exp_date: Optional[str] = None
    qty: Optional[float] = None
    free_qty: Optional[float] = None
    mrp: Optional[float] = None
    rate: Optional[float] = None
    discount_pct: Optional[float] = None
    special_discount_pct: Optional[float] = None
    gst_pct: Optional[float] = None
    amount: Optional[float] = None
    computed_cost_per_unit: Optional[float] = None
    match_confidence: Optional[float] = None
    match_status: str
    medicine_id: Optional[int] = None
    suggested_medicine_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class BillItemEdit(BaseModel):
    id: int
    raw_name: Optional[str] = None
    qty: Optional[float] = Field(default=None, ge=0)
    free_qty: Optional[float] = Field(default=None, ge=0)
    mrp: Optional[float] = Field(default=None, ge=0)
    rate: Optional[float] = Field(default=None, ge=0)
    discount_pct: Optional[float] = Field(default=None, ge=0, le=100)
    special_discount_pct: Optional[float] = Field(default=None, ge=0, le=100)
    gst_pct: Optional[float] = Field(default=None, ge=0, le=100)
    exp_date: Optional[str] = None
    medicine_id: Optional[int] = None
    apply_to_master_list: bool = True

    @field_validator("qty", "free_qty", "mrp", "rate", "discount_pct",
                      "special_discount_pct", "gst_pct", mode="before")
    @classmethod
    def _reject_blank_strings(cls, v):
        if v == "" or v is None:
            return None
        return v


class BillOut(BaseModel):
    id: int
    distributor_name: Optional[str] = None
    invoice_no: Optional[str] = None
    invoice_date: Optional[datetime] = None
    year: Optional[int] = None
    month: Optional[int] = None
    total_amount: Optional[float] = None
    status: str
    uploaded_at: datetime
    ocr_confidence: Optional[float] = None
    needs_attention_reason: Optional[str] = None
    processing_error: Optional[str] = None
    items: List[BillItemOut] = []

    model_config = ConfigDict(from_attributes=True)


class BillStatusOut(BaseModel):
    id: int
    status: str
    ocr_confidence: Optional[float] = None
    needs_attention_reason: Optional[str] = None
    processing_error: Optional[str] = None


class UploadAcceptedResponse(BaseModel):
    bill_id: int
    task_id: str
    status: str
    duplicate_warning: Optional[str] = None


class ConfirmBillRequest(BaseModel):
    bill_id: int
    items: List[BillItemEdit]
    invoice_no: Optional[str] = None
    distributor_name: Optional[str] = None


class SmartThresholdSuggestion(BaseModel):
    medicine_id: int
    medicine_name: Optional[str] = None
    avg_daily_sales: float
    std_dev_daily_sales: float
    lead_time_days: int
    window_days: int
    sale_days_in_window: int
    total_units_sold_in_window: float
    has_sufficient_data: bool
    suggested_threshold: Optional[int] = None
    current_threshold: Optional[float] = None
    reason: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class LeadTimeUpdate(BaseModel):
    lead_time_days: Optional[int] = Field(default=None, ge=1)



class ChangeSummaryItem(BaseModel):
    medicine_name: str
    field: str
    old_value: Optional[float] = None
    new_value: Optional[float] = None


class RegionOcrRequest(BaseModel):
    x0: int = Field(ge=0)
    y0: int = Field(ge=0)
    x1: int = Field(ge=0)
    y1: int = Field(ge=0)

    @field_validator("x1")
    @classmethod
    def _x1_after_x0(cls, v, info):
        if "x0" in info.data and v <= info.data["x0"]:
            raise ValueError("x1 must be greater than x0")
        return v

    @field_validator("y1")
    @classmethod
    def _y1_after_y0(cls, v, info):
        if "y0" in info.data and v <= info.data["y0"]:
            raise ValueError("y1 must be greater than y0")
        return v


class RegionOcrResponse(BaseModel):
    text: str
    confidence: float

class SaleCreate(BaseModel):
    medicine_id: int
    qty_sold: float = Field(gt=0, description="Must be greater than 0")


class LastPurchaseInfo(BaseModel):
    distributor_id: Optional[int] = None
    distributor_name: Optional[str] = None
    qty_received: Optional[float] = None
    free_qty_received: Optional[float] = None
    rate: Optional[float] = None
    mrp: Optional[float] = None
    purchase_date: Optional[datetime] = None


class StockSnapshot(BaseModel):
    medicine_id: int
    medicine_name: str
    current_stock: float
    low_stock_threshold: Optional[float] = None
    last_purchase: Optional[LastPurchaseInfo] = None
    sale_id: Optional[int] = None


class ReorderMedicineItem(BaseModel):
    id: Optional[int] = None
    medicine_id: Optional[int] = None
    name: str
    current_stock: Optional[float] = None
    low_stock_threshold: Optional[float] = None
    last_qty_received: Optional[float] = None
    last_rate: Optional[float] = None
    last_purchase_date: Optional[datetime] = None
    quantity_needed: Optional[float] = None
    note: Optional[str] = None
    source: str


class DistributorReorderGroup(BaseModel):
    distributor_id: Optional[int] = None
    distributor_name: str
    items: List[ReorderMedicineItem]


class ManualReorderCreate(BaseModel):
    medicine_id: Optional[int] = None
    custom_name: Optional[str] = None
    distributor_id: Optional[int] = None
    distributor_name_new: Optional[str] = None
    quantity_needed: Optional[float] = Field(default=None, gt=0)
    note: Optional[str] = None


class ThresholdUpdate(BaseModel):
    low_stock_threshold: float = Field(ge=0)

class ExpiryBatchOut(BaseModel):
    batch_id: int
    medicine_id: int
    medicine_name: str
    batch_no: Optional[str] = None
    expiry_date: Optional[date] = None
    days_remaining: int
    urgency: str
    qty_received: float
    distributor_name: Optional[str] = None


class MissingExpiryBatch(BaseModel):
    batch_id: int
    medicine_id: int
    medicine_name: str
    batch_no: Optional[str] = None
    qty_received: float
    distributor_name: Optional[str] = None


class ExpirySummary(BaseModel):
    expired: int
    critical: int
    warning: int
    missing_expiry: int


class FillExpiryRequest(BaseModel):
    expiry_date: date

class MonthlySpendPoint(BaseModel):
    year: int
    month: int
    label: str
    total_spend: float


class DistributorBreakdownItem(BaseModel):
    distributor_id: Optional[int] = None
    distributor_name: str
    total_spend: float
    bill_count: int


class PriceChangeItem(BaseModel):
    medicine_id: int
    medicine_name: str
    old_rate: float
    new_rate: float
    pct_change: float
    change_count: int


class TopSpendItem(BaseModel):
    medicine_id: int
    medicine_name: str
    total_spend: float


class TopSellingItem(BaseModel):
    medicine_id: int
    medicine_name: str
    qty_sold: float


class AnalyticsOverview(BaseModel):
    this_month_spend: float
    last_month_spend: float
    spend_change_pct: Optional[float] = None
    confirmed_bills_this_month: int
    distributors_used_this_month: int
    avg_bill_value: float
    stock_value: float
    low_stock_count: int
    pending_review_count: int
    expiring_critical: int

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str
    full_name: Optional[str] = None


class UserOut(BaseModel):
    id: int
    username: str
    full_name: Optional[str] = None
    role: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6)
    full_name: Optional[str] = None
    role: str = Field(pattern="^(owner|staff)$")


class BarcodeAssignRequest(BaseModel):
    barcode: str = Field(min_length=3, max_length=64)


class BarcodeLookupResult(BaseModel):
    found: bool
    medicine: Optional[MedicineOut] = None
    stock: Optional[StockSnapshot] = None


class GstSlabBreakdown(BaseModel):
    gst_pct: float
    taxable_amount: float
    cgst: float
    sgst: float
    total_tax: float
    total_amount: float
    item_count: int


class GstReport(BaseModel):
    year: int
    month: int
    month_label: str
    slabs: list[GstSlabBreakdown]
    grand_taxable_amount: float
    grand_cgst: float
    grand_sgst: float
    grand_total_tax: float
    grand_total_amount: float
    bill_count: int


# ---------------------------------------------------------------------------
# Substitute Medicine Suggestion
# ---------------------------------------------------------------------------
class CompositionUpdate(BaseModel):
    composition: str = Field(min_length=1, max_length=500)


class SubstituteMedicineItem(BaseModel):
    medicine_id: int
    particulars: str
    company: Optional[str] = None
    unit: Optional[str] = None
    mrp: Optional[float] = None
    current_stock: float
    composition: Optional[str] = None
    match_type: str   # "exact" | "partial"
    matched_salts: int
    query_salts: int


class MedicineSubstituteSource(BaseModel):
    id: int
    particulars: str
    composition: Optional[str] = None


class MedicineSubstituteResult(BaseModel):
    medicine: MedicineSubstituteSource
    substitutes: list[SubstituteMedicineItem]


class SaltAvailability(BaseModel):
    exists_in_catalog: bool
    in_stock_count: int
    out_of_stock_count: int

# ---------------------------------------------------------------------------
# PharmaGraph (Pillar 1)
# ---------------------------------------------------------------------------
class GraphSaltRef(BaseModel):
    salt: str


class GraphInteraction(BaseModel):
    salt: str
    interacts_with: str
    severity: Optional[str] = None
    note: Optional[str] = None


class GraphTreats(BaseModel):
    salt: str
    condition: str


class GraphSubstituteRef(BaseModel):
    medicine_id: int
    particulars: str
    company: Optional[str] = None
    current_stock: float
    weight: Optional[float] = None


class GraphDistributorRef(BaseModel):
    distributor_id: int
    name: str


class MedicineGraph(BaseModel):
    medicine_id: int
    particulars: str
    composition: Optional[str] = None
    contains: list[GraphSaltRef]
    interacts_with: list[GraphInteraction]
    treats: list[GraphTreats]
    substitutes: list[GraphSubstituteRef]
    supplied_by: list[GraphDistributorRef]


class InteractionCheckResult(BaseModel):
    salt_a: str
    salt_b: str
    severity: str
    note: str


class ConditionMedicineItem(BaseModel):
    medicine_id: int
    particulars: str
    company: Optional[str] = None
    composition: Optional[str] = None
    current_stock: float
    mrp: Optional[float] = None


class GraphRebuildResponse(BaseModel):
    task_id: str
    status: str


class GraphRebuildStatus(BaseModel):
    status: str
    stats: Optional[dict] = None
    error: Optional[str] = None

# ---------------------------------------------------------------------------
# PharmaCopilot (Pillar 2)
# ---------------------------------------------------------------------------
class CopilotChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[dict] = Field(default_factory=list)


class CopilotToolCall(BaseModel):
    tool: str
    input: dict
    error: Optional[str] = None


class CopilotChatResponse(BaseModel):
    reply: str
    tool_calls: list[CopilotToolCall]
    history: list[dict]

# ---------------------------------------------------------------------------
# Point of Sale / Safety Guardrail (Pillar 3)
# ---------------------------------------------------------------------------
class CartItemInput(BaseModel):
    medicine_id: int
    qty_sold: float = Field(gt=0)



class CartSaleRequest(BaseModel):
    items: list[CartItemInput] = Field(min_length=1)
    confirm_override: bool = False
    customer_id: Optional[int] = None                                   # NEW (Pillar 5)
    payment_mode: str = Field(default="cash", pattern="^(cash|credit)$")  # NEW (Pillar 5)
 
 
class CartInteractionFlag(BaseModel):
    salt_a: str
    salt_b: str
    severity: str
    note: str
 
 
class CartItemDetail(BaseModel):
    medicine_id: int
    particulars: str
    salts: list[str]
 
 
class CartSaleResponse(BaseModel):
    status: str
    has_interactions: bool
    interactions: list[CartInteractionFlag]
    items: list[CartItemDetail]
    results: list[dict] = Field(default_factory=list)
    total_value: Optional[float] = None            # NEW (Pillar 5)
    payment_mode: Optional[str] = None              # NEW (Pillar 5)
    credit_balance_after: Optional[float] = None    # NEW (Pillar 5)

# ---------------------------------------------------------------------------
# TrustChain — Tamper-Evident Audit Trail (Pillar 4)
# ---------------------------------------------------------------------------
class AuditLedgerEntryOut(BaseModel):
    id: int
    event_type: str
    reference_id: Optional[int] = None
    payload: dict
    payload_hash: str
    previous_hash: str
    entry_hash: str
    created_at: datetime
 
 
class BrokenLedgerEntry(BaseModel):
    id: int
    event_type: str
    reference_id: Optional[int] = None
    created_at: Optional[str] = None
    problems: list[str]
 
 
class AuditVerifyResult(BaseModel):
    total_entries: int
    is_valid: bool
    broken_entries: list[BrokenLedgerEntry]
    verified_at: str


# ---------------------------------------------------------------------------
# Customer Health Companion (Pillar 5, Part A)
# ---------------------------------------------------------------------------
class CustomerCreate(BaseModel):
    phone: str = Field(min_length=6, max_length=15)
    name: Optional[str] = None
    consent_given: bool = False
 
 
class CustomerOut(BaseModel):
    customer_id: int
    phone: str
    name: Optional[str] = None
    consent_given_at: Optional[datetime] = None
    current_balance: float
    total_purchases: int
    last_visit: Optional[datetime] = None
 
 
class CreditChargeRequest(BaseModel):
    amount: float = Field(gt=0)
    note: Optional[str] = None
 
 
class CreditPaymentRequest(BaseModel):
    amount: float = Field(gt=0)
    note: Optional[str] = None
 
 
class CustomerCreditEntryOut(BaseModel):
    id: int
    change_amount: float
    resulting_balance: float
    reason: str
    note: Optional[str] = None
    created_at: datetime
 
    model_config = ConfigDict(from_attributes=True)
 
 
class OutstandingBalanceItem(BaseModel):
    customer_id: int
    phone: str
    name: Optional[str] = None
    current_balance: float
 
 
class AdherenceAlertOut(BaseModel):
    customer_id: int
    customer_name: Optional[str] = None
    customer_phone: str
    medicine_id: int
    medicine_name: str
    avg_gap_days: float
    days_since_last_purchase: int
    days_overdue: float
    last_purchase_date: datetime
    purchase_count: int
 
 
# ---------------------------------------------------------------------------
# Symptom-to-Stock Bot (Pillar 5, Part A.3)
# ---------------------------------------------------------------------------
class SymptomQueryRequest(BaseModel):
    message: str = Field(min_length=2, max_length=500)
 
 
class SymptomQueryResponse(BaseModel):
    matched: bool
    conditions: list[str]
    suggestions: dict[str, list[ConditionMedicineItem]]   # reuses Pillar 1's existing schema
    reply: str
    disclaimer: str
 
 
# ---------------------------------------------------------------------------
# Inter-Pharmacy Network (Pillar 5, Part B)
# ---------------------------------------------------------------------------
class PharmacyNodeOut(BaseModel):
    id: int
    shop_name: str
    api_base_url: Optional[str] = None
    contact_phone: Optional[str] = None
    is_self: bool
    opted_in: bool
    joined_at: Optional[datetime] = None
 
    model_config = ConfigDict(from_attributes=True)
 
 
class PharmacyNodeCreate(BaseModel):
    shop_name: str = Field(min_length=2, max_length=150)
    api_base_url: Optional[str] = None
    contact_phone: Optional[str] = None
 
 
class NetworkListingCreate(BaseModel):
    listing_type: str = Field(pattern="^(excess_stock|shortage_request)$")
    medicine_name: str = Field(min_length=1, max_length=255)
    composition: Optional[str] = None
    quantity: Optional[float] = Field(default=None, gt=0)
    expiry_date: Optional[date] = None
    note: Optional[str] = None
 
 
class NetworkListingOut(BaseModel):
    id: int
    pharmacy_node_id: int
    pharmacy_shop_name: str
    listing_type: str
    medicine_name: str
    composition: Optional[str] = None
    quantity: Optional[float] = None
    expiry_date: Optional[date] = None
    note: Optional[str] = None
    status: str
    claimed_by_node_id: Optional[int] = None
    claimed_by_shop_name: Optional[str] = None
    created_at: datetime
 
 
class ClaimListingRequest(BaseModel):
    claiming_node_id: int