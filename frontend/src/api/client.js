const BASE = "/api";
const TOKEN_KEY = "kush_medical_token";


// ---------------------------------------------------------------------------
// Auth token helpers - a real standalone app (not a claude.ai artifact), so
// localStorage is the right place for this: it survives page refreshes,
// which is what you want for "stay logged in" behavior.
// ---------------------------------------------------------------------------
export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}
export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

// Fired whenever a request comes back 401 (expired/invalid session) so the
// app shell can redirect to /login without every single page needing to
// handle this itself.
let onUnauthorized = () => {};
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

async function apiFetch(path, options = {}) {
  const token = getToken();
  const headers = { ...(options.headers || {}) };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, { ...options, headers });
  

  if (res.status === 401) {
    clearToken();
    onUnauthorized();
    throw new Error("Session expired — please log in again.");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }
  if (res.status === 204) return null;
  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/pdf")) return res.blob();
  return res.json();
}

function jsonBody(payload) {
  return { headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) };
}

export const api = {
  // --- Auth ---
  login: (username, password) =>
    apiFetch("/auth/login", { method: "POST", ...jsonBody({ username, password }) }),
  me: () => apiFetch("/auth/me"),
  listUsers: () => apiFetch("/auth/users"),
  createUser: (payload) => apiFetch("/auth/users", { method: "POST", ...jsonBody(payload) }),
  deactivateUser: (id) => apiFetch(`/auth/users/${id}/deactivate`, { method: "PATCH" }),
  sendCopilotMessage: (message, history) =>
    apiFetch("/copilot/chat", { method: "POST", ...jsonBody({ message, history }) }),

  // --- Bills ---
  uploadBill: (formData) => apiFetch("/bills/upload", { method: "POST", body: formData }),
  uploadBillsBatch: (formData) => apiFetch("/bills/upload-batch", { method: "POST", body: formData }),
  getBillStatus: (id) => apiFetch(`/bills/${id}/status`),
  getBill: (id) => apiFetch(`/bills/${id}`),
  getBillImageUrl: (id) => `${BASE}/bills/${id}/image?token=${encodeURIComponent(getToken() || "")}`,
  listBills: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return apiFetch(`/bills${qs ? "?" + qs : ""}`);
  },
  confirmBill: (payload) => apiFetch("/bills/confirm", { method: "POST", ...jsonBody(payload) }),
  reprocessRegion: (billId, box) =>
    apiFetch(`/bills/${billId}/reprocess-region`, { method: "POST", ...jsonBody(box) }),

  // --- Medicines ---
  browseMedicines: ({ q = "", page = 1, page_size = 50 } = {}) => {
    const params = new URLSearchParams({ page, page_size });
    if (q) params.set("q", q);
    return apiFetch(`/medicines?${params.toString()}`);
  },
  getMedicineHistory: (id) => apiFetch(`/medicines/${id}/history`),
  lookupBarcode: (code) => apiFetch(`/medicines/barcode/${encodeURIComponent(code)}`),
  assignBarcode: (medicineId, barcode) =>
    apiFetch(`/medicines/${medicineId}/barcode`, { method: "PATCH", ...jsonBody({ barcode }) }),
  updateComposition: (medicineId, composition) =>
    apiFetch(`/medicines/${medicineId}/composition`, { method: "PATCH", ...jsonBody({ composition }) }),

  // --- Substitute Medicine Suggestion ---
  searchSubstitutes: (q, inStockOnly = true) =>
    apiFetch(`/substitutes/search?q=${encodeURIComponent(q)}&in_stock_only=${inStockOnly}`),
  getSubstitutesForMedicine: (medicineId, inStockOnly = true) =>
    apiFetch(`/substitutes/for-medicine/${medicineId}?in_stock_only=${inStockOnly}`),
  checkSaltAvailability: (q) => apiFetch(`/substitutes/availability?q=${encodeURIComponent(q)}`),

  // --- PharmaGraph (Pillar 1) ---
  getMedicineGraph: (medicineId) => apiFetch(`/graph/medicine/${medicineId}`),
  checkInteractions: (saltNames) => apiFetch(`/graph/check-interactions?salts=${encodeURIComponent(saltNames.join(","))}`),
  getMedicinesForCondition: (condition, inStockOnly = true) =>
    apiFetch(`/graph/condition/${encodeURIComponent(condition)}?in_stock_only=${inStockOnly}`),
  triggerGraphRebuild: () => apiFetch("/graph/rebuild", { method: "POST" }),
  getGraphRebuildStatus: (taskId) => apiFetch(`/graph/rebuild/${taskId}/status`),

  dashboardSummary: () => apiFetch("/dashboard/summary"),

  // --- Stock, sales, reorder list ---
  getStockSnapshot: (medicineId) => apiFetch(`/stock/medicine/${medicineId}/snapshot`),
  recordSale: (medicineId, qtySold) =>
    apiFetch("/stock/sales", { method: "POST", ...jsonBody({ medicine_id: medicineId, qty_sold: qtySold }) }),
  getReorderList: () => apiFetch("/stock/reorder-list"),
  addManualReorderItem: (payload) => apiFetch("/stock/reorder-list/manual", { method: "POST", ...jsonBody(payload) }),
  removeReorderItem: (id) => apiFetch(`/stock/reorder-list/${id}`, { method: "DELETE" }),
  updateLowStockThreshold: (medicineId, threshold) =>
    apiFetch(`/stock/medicine/${medicineId}/threshold`, { method: "PATCH", ...jsonBody({ low_stock_threshold: threshold }) }),
  recordStockAdjustment: (medicineId, newTotalStock, note) =>
    apiFetch("/stock/adjustments", { method: "POST", ...jsonBody({ medicine_id: medicineId, new_total_stock: newTotalStock, note }) }),

  // --- Expiry tracking ---
  getExpiryDashboard: (days = 90) => apiFetch(`/expiry/dashboard?days=${days}`),
  getExpirySummary: () => apiFetch("/expiry/summary"),
  getMissingExpiry: () => apiFetch("/expiry/missing"),
  fillExpiry: (batchId, expiryDate) =>
    apiFetch(`/expiry/batch/${batchId}`, { method: "PATCH", ...jsonBody({ expiry_date: expiryDate }) }),

  // --- Analytics (owner only) ---
  getAnalyticsOverview: () => apiFetch("/analytics/overview"),
  getMonthlySpend: (months = 6) => apiFetch(`/analytics/monthly-spend?months=${months}`),
  getDistributorBreakdown: (year, month) => {
    const params = new URLSearchParams();
    if (year) params.set("year", year);
    if (month) params.set("month", month);
    return apiFetch(`/analytics/distributor-breakdown?${params.toString()}`);
  },
  getPriceChanges: (days = 90, limit = 10) => apiFetch(`/analytics/price-changes?days=${days}&limit=${limit}`),
  getTopMedicinesBySpend: (year, month, limit = 10) => {
    const params = new URLSearchParams({ limit });
    if (year) params.set("year", year);
    if (month) params.set("month", month);
    return apiFetch(`/analytics/top-medicines-by-spend?${params.toString()}`);
  },
  getTopSelling: (days = 30, limit = 10) => apiFetch(`/analytics/top-selling?days=${days}&limit=${limit}`),

  // --- GST reports (owner only) ---
  getGstReport: (year, month) => {
    const params = new URLSearchParams();
    if (year) params.set("year", year);
    if (month) params.set("month", month);
    return apiFetch(`/gst/report?${params.toString()}`);
  },
  downloadGstReportPdf: async (year, month) => {
    const params = new URLSearchParams();
    if (year) params.set("year", year);
    if (month) params.set("month", month);
    const blob = await apiFetch(`/gst/report/pdf?${params.toString()}`);
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `GST_Report_${year}_${month}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  },
  getHealth: () => apiFetch("/health"),

  // --- Point of Sale Safety Guardrail (Pillar 3) ---
  checkCart: (items) => apiFetch("/pos/check-cart", { method: "POST", ...jsonBody({ items }) }),
  recordCartSale: (items, confirmOverride = false) =>
    apiFetch("/pos/sales", { method: "POST", ...jsonBody({ items, confirm_override: confirmOverride , customer_id: customerId, payment_mode: paymentMode }), }),

  // --- TrustChain / tamper-evident audit ledger (Pillar 4, owner only) ---
  getAuditLedger: ({ event_type, limit = 100 } = {}) => {
    const params = new URLSearchParams({ limit });
    if (event_type) params.set("event_type", event_type);
    return apiFetch(`/audit/ledger?${params.toString()}`);
  },
  verifyAuditChain: () => apiFetch("/audit/verify"),
  getAuditEntriesFor: (eventType, referenceId) => apiFetch(`/audit/for/${eventType}/${referenceId}`),

   // --- Customer Health Companion (Pillar 5, Part A) ---
  searchCustomers: (q = "") => apiFetch(`/customers${q ? "?q=" + encodeURIComponent(q) : ""}`),
  getCustomer: (id) => apiFetch(`/customers/${id}`),
  createOrGetCustomer: (payload) => apiFetch("/customers", { method: "POST", ...jsonBody(payload) }),
  getCustomerLedger: (id) => apiFetch(`/customers/${id}/ledger`),
  chargeCustomerCredit: (id, amount, note) =>
    apiFetch(`/customers/${id}/credit/charge`, { method: "POST", ...jsonBody({ amount, note }) }),
  recordCustomerPayment: (id, amount, note) =>
    apiFetch(`/customers/${id}/credit/payment`, { method: "POST", ...jsonBody({ amount, note }) }),
  getOutstandingBalances: () => apiFetch("/customers/outstanding"),
  getAdherenceAlerts: () => apiFetch("/customers/adherence-alerts"),
 
  // --- Symptom-to-Stock Bot (Pillar 5, Part A.3) ---
  querySymptomBot: (message) => apiFetch("/symptom-bot/query", { method: "POST", ...jsonBody({ message }) }),
 
  // --- Inter-Pharmacy Network (Pillar 5, Part B) ---
  getNetworkNodes: () => apiFetch("/network/nodes"),
  addNetworkNode: (payload) => apiFetch("/network/nodes", { method: "POST", ...jsonBody(payload) }),
  getNetworkListings: (listingType = "", status = "open") => {
    const params = new URLSearchParams({ status });
    if (listingType) params.set("listing_type", listingType);
    return apiFetch(`/network/listings?${params.toString()}`);
  },
  createNetworkListing: (payload) => apiFetch("/network/listings", { method: "POST", ...jsonBody(payload) }),
  publishNearExpiryListings: (days = 60) => apiFetch(`/network/listings/publish-near-expiry?days=${days}`, { method: "POST" }),
  claimNetworkListing: (listingId, claimingNodeId) =>
    apiFetch(`/network/listings/${listingId}/claim`, { method: "POST", ...jsonBody({ claiming_node_id: claimingNodeId }) }),
  fulfillNetworkListing: (listingId) => apiFetch(`/network/listings/${listingId}/fulfill`, { method: "POST" }),
  withdrawNetworkListing: (listingId) => apiFetch(`/network/listings/${listingId}`, { method: "DELETE" }),
};


