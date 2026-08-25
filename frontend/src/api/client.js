const BASE = "/api";
const TOKEN_KEY = "kush_medical_token";
const REFRESH_TOKEN_KEY = "kush_medical_refresh_token";


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
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}
export function getRefreshToken() {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}
export function setRefreshToken(token) {
  if (token) localStorage.setItem(REFRESH_TOKEN_KEY, token);
}

// Fired whenever a request comes back 401 (expired/invalid session) so the
// app shell can redirect to /login without every single page needing to
// handle this itself.
let onUnauthorized = () => {};
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

let _refreshing = null;  // singleton refresh promise — prevents race of multiple 401s

async function attemptSilentRefresh() {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;

  if (!_refreshing) {
    _refreshing = fetch(`${BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    }).then(async (res) => {
      if (!res.ok) return false;
      const data = await res.json();
      setToken(data.access_token);
      return true;
    }).catch(() => false).finally(() => { _refreshing = null; });
  }
  return _refreshing;
}

async function apiFetch(path, options = {}) {
  const token = getToken();
  const headers = { ...(options.headers || {}) };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, { ...options, headers });

  if (res.status === 401) {
    // Priority 2a: Try silent refresh before giving up
    const refreshed = await attemptSilentRefresh();
    if (refreshed) {
      // Retry the original request with the new token
      const newToken = getToken();
      const retryHeaders = { ...(options.headers || {}) };
      if (newToken) retryHeaders["Authorization"] = `Bearer ${newToken}`;
      const retryRes = await fetch(`${BASE}${path}`, { ...options, headers: retryHeaders });
      if (retryRes.status === 401) {
        clearToken();
        onUnauthorized();
        throw new Error("Session expired — please log in again.");
      }
      if (!retryRes.ok) {
        const body = await retryRes.json().catch(() => ({}));
        throw new Error(body.detail || `Request failed (${retryRes.status})`);
      }
      if (retryRes.status === 204) return null;
      const ct = retryRes.headers.get("content-type") || "";
      if (ct.includes("application/pdf")) return retryRes.blob();
      return retryRes.json();
    }
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
  refresh: (refresh_token) =>
    apiFetch("/auth/refresh", { method: "POST", ...jsonBody({ refresh_token }) }),
  logout: (refresh_token) =>
    apiFetch("/auth/logout", { method: "DELETE", ...jsonBody({ refresh_token }) }),
  me: () => apiFetch("/auth/me"),
  listUsers: () => apiFetch("/auth/users"),
  createUser: (payload) => apiFetch("/auth/users", { method: "POST", ...jsonBody(payload) }),
  deactivateUser: (id) => apiFetch(`/auth/users/${id}/deactivate`, { method: "PATCH" }),
  sendCopilotMessage: (message, history) =>
    apiFetch("/copilot/chat", { method: "POST", ...jsonBody({ message, history }) }),

  // --- Bills ---
  // Note: Do not set Content-Type manually for FormData; fetch will set multipart/form-data with the correct boundary automatically.
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
  reprocessRegion: (billId, { x0, y0, x1, y1 }) =>
    apiFetch(`/bills/${billId}/reprocess-region`, { method: "POST", ...jsonBody({ x0, y0, x1, y1 }) }),
  addBillItem: (billId) => apiFetch(`/bills/${billId}/items`, { method: "POST" }),
  removeBillItem: (billId, itemId) => apiFetch(`/bills/${billId}/items/${itemId}`, { method: "DELETE" }),

  // --- Medicines ---
  browseMedicines: ({ q = "", page = 1, page_size = 50 } = {}) => {
    const params = new URLSearchParams({ page, page_size });
    if (q) params.set("q", q);
    return apiFetch(`/medicines?${params.toString()}`);
  },
  createMedicine: (payload) => apiFetch("/medicines", { method: "POST", ...jsonBody(payload) }),
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
  // FIX: Stock.jsx calls api.fulfillReorderItem — add the missing method (PATCH /stock/reorder-list/{id}/fulfill)
  fulfillReorderItem: (id) => apiFetch(`/stock/reorder-list/${id}/fulfill`, { method: "PATCH" }),
  updateLowStockThreshold: (medicineId, threshold) =>
    apiFetch(`/stock/medicine/${medicineId}/threshold`, { method: "PATCH", ...jsonBody({ low_stock_threshold: threshold }) }),
  // FIX: Stock.jsx calls api.recordAdjustment({medicine_id, new_total_stock, note})
  // The backend POST /stock/adjustments accepts exactly those fields
  recordAdjustment: ({ medicine_id, new_total_stock, note } = {}) =>
    apiFetch("/stock/adjustments", { method: "POST", ...jsonBody({ medicine_id, new_total_stock, note }) }),
  // Alias kept for any other callers using the old name
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
  recordCartSale: (items, confirmOverride = false, customerId = null, paymentMode = "cash") =>
    apiFetch("/pos/sales", {
      method: "POST",
      ...jsonBody({ items, confirm_override: confirmOverride, customer_id: customerId, payment_mode: paymentMode }),
    }),

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

  // --- Predictive Intelligence (Pillar 6) ---
  getDemandForecast: (medicineId, periods = 14, historyDays = 180) =>
    apiFetch(`/forecast/medicine/${medicineId}?periods=${periods}&history_days=${historyDays}`),
  getPriceJumpAnomalies: (days = 180) => apiFetch(`/anomalies/price-jumps?days=${days}`),
  getStockAdjustmentAnomalies: (days = 90) => apiFetch(`/anomalies/stock-adjustments?days=${days}`),
  explainAnomaly: (anomaly) => apiFetch("/anomalies/explain", { method: "POST", ...jsonBody({ anomaly }) }),

  // --- Notification Engine (Priority 1) ---
  getNotifications: ({ unread_only = false, limit = 20, offset = 0 } = {}) => {
    const params = new URLSearchParams({ limit, offset });
    if (unread_only) params.set("unread_only", "true");
    return apiFetch(`/notifications?${params.toString()}`);
  },
  getUnreadCount: () => apiFetch("/notifications/unread-count"),
  markNotificationRead: (id) => apiFetch(`/notifications/${id}/read`, { method: "PATCH" }),
  markAllNotificationsRead: () => apiFetch("/notifications/read-all", { method: "POST" }),
  sendDigestNow: () => apiFetch("/notifications/digest/send-now", { method: "POST" }),
  // --- Cold-Chain Compliance ---
  getColdChainUnits: () => apiFetch("/cold-chain/units"),
  createColdChainUnit: (payload) => apiFetch("/cold-chain/units", { method: "POST", ...jsonBody(payload) }),
  updateColdChainUnit: (unitId, payload) => apiFetch(`/cold-chain/units/${unitId}`, { method: "PUT", ...jsonBody(payload) }),
  recordColdChainReading: (payload) => apiFetch("/cold-chain/readings", { method: "POST", ...jsonBody(payload) }),
  getColdChainReadings: (unitId, hours = 24) => apiFetch(`/cold-chain/readings/${unitId}?hours=${hours}`),
  getColdChainCompliance: (days = 30, unitId = null) => {
      const params = new URLSearchParams({ days });
      if (unitId) params.set("unit_id", unitId);
      return apiFetch(`/cold-chain/compliance?${params.toString()}`);
  },
  getCompromisedBatches: (unitId) => apiFetch(`/cold-chain/compromised/${unitId}`),
  toggleBatchColdChain: (batchId, isColdChain) => apiFetch(`/cold-chain/batches/${batchId}/cold-chain`, { method: "PATCH", ...jsonBody({ is_cold_chain: isColdChain }) }),

  // --- Syndromic Surveillance (owner only) ---
  getSurveillanceConditions: () => apiFetch("/surveillance/conditions"),
  getSurveillanceTrend: (condition, days = 30) =>
      apiFetch(`/surveillance/trend/${encodeURIComponent(condition)}?days=${days}`),
  getSurveillanceSpikes: (days = 14, zThreshold = 2.0) =>
      apiFetch(`/surveillance/spikes?days=${days}&z_threshold=${zThreshold}`),
  triggerSurveillanceScan: () => apiFetch("/surveillance/scan-now", { method: "POST" }),

  // Feature 4: Supply Chain Trust Score
  getTrustScores: () => apiFetch('/trust-score/distributors'),
  getTrustScore: (id, medicineId) => {
    const params = new URLSearchParams();
    if (medicineId) params.set("medicine_id", medicineId);
    return apiFetch(`/trust-score/distributors/${id}?${params.toString()}`);
  },
  getBatchCollisions: (days = 365) => apiFetch(`/trust-score/batch-collisions?days=${days}`),
  getRateConsistency: (medicineId) => apiFetch(`/trust-score/medicine/${medicineId}/rate-consistency`),

  // --- Smart Purchase AI (Feature 12, owner only) ---
  getSmartPurchaseOrder: () => apiFetch("/smart-purchase/order"),
  getSmartPurchaseDetail: (medicineId) => apiFetch(`/smart-purchase/order/${medicineId}`),
  sendSmartPurchaseWhatsApp: (payload) =>
    apiFetch("/smart-purchase/send-whatsapp", { method: "POST", ...jsonBody(payload) }),

  // --- Profit Margin Optimizer (Feature 13, owner only) ---
  getProfitMargins: () => apiFetch("/profit/margins"),
  /**
   * @param {Object} opts
   * @param {"mild"|"moderate"|"severe"|null} opts.severity
   * @param {number} opts.days
   */
  getProfitCompression: ({ severity = null, days = 90 } = {}) => {
    const params = new URLSearchParams({ days });
    if (severity) params.set("severity", severity);
    return apiFetch(`/profit/compression?${params.toString()}`);
  },
  getBestMarginSubstitutes: (medicineId) => apiFetch(`/profit/substitutes/${medicineId}`),
  getDistributorNegotiationReport: () => apiFetch("/profit/distributor-report"),

  // --- Prescription Intelligence Engine (PIE) ---
  uploadPrescription: (formData) =>
    apiFetch("/prescriptions/upload", { method: "POST", body: formData }),
  listPrescriptions: ({ status, customer_id, limit = 50, offset = 0 } = {}) => {
    const params = new URLSearchParams({ limit, offset });
    if (status) params.set("status", status);
    if (customer_id) params.set("customer_id", customer_id);
    return apiFetch(`/prescriptions?${params.toString()}`);
  },
  getPrescription: (id) => apiFetch(`/prescriptions/${id}`),
  getUncollectedPrescriptions: (minutes = 30) =>
    apiFetch(`/prescriptions/uncollected?minutes=${minutes}`),
  markPrescriptionItemAddedToCart: (prescriptionId, itemId) =>
    apiFetch(`/prescriptions/${prescriptionId}/items/${itemId}/add-to-cart`, { method: "PATCH" }),
  linkPrescriptionItemMedicine: (prescriptionId, itemId, medicineId) =>
    apiFetch(`/prescriptions/${prescriptionId}/items/${itemId}/link`, { method: "PATCH", ...jsonBody({ medicine_id: medicineId }) }),
  convertPrescription: (prescriptionId) =>
    apiFetch("/prescriptions/convert", { method: "POST", ...jsonBody({ prescription_id: prescriptionId }) }),
  abandonPrescription: (prescriptionId) =>
    apiFetch(`/prescriptions/${prescriptionId}/abandon`, { method: "POST" }),
};
