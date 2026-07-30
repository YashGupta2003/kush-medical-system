const BASE = "/api";
const TOKEN_KEY = "kush_medical_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}
export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

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
    const err = new Error(body.detail || `Request failed (${res.status})`);
    err.status = res.status;
    throw err;
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
  // --- System Health ---
  getHealth: () => apiFetch("/health"),

  // --- Auth & Users ---
  login: (username, password) =>
    apiFetch("/auth/login", { method: "POST", ...jsonBody({ username, password }) }),
  me: () => apiFetch("/auth/me"),
  listUsers: () => apiFetch("/auth/users"),
  createUser: (payload) => apiFetch("/auth/users", { method: "POST", ...jsonBody(payload) }),
  deactivateUser: (id) => apiFetch(`/auth/users/${id}/deactivate`, { method: "PATCH" }),

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
  addBillItem: (billId) => apiFetch(`/bills/${billId}/items`, { method: "POST" }),
  removeBillItem: (billId, itemId) => apiFetch(`/bills/${billId}/items/${itemId}`, { method: "DELETE" }),

  // --- Medicines ---
  browseMedicines: ({ q = "", page = 1, page_size = 50 } = {}) => {
    const params = new URLSearchParams({ page, page_size });
    if (q) params.set("q", q);
    return apiFetch(`/medicines?${params.toString()}`);
  },
  createMedicine: (payload) => apiFetch("/medicines", { method: "POST", ...jsonBody(payload) }),
  updateMedicine: (id, payload) => apiFetch(`/medicines/${id}`, { method: "PUT", ...jsonBody(payload) }),
  getMedicineHistory: (id) => apiFetch(`/medicines/${id}/history`),
  lookupBarcode: (code) => apiFetch(`/medicines/barcode/${encodeURIComponent(code)}`),
  assignBarcode: (medicineId, barcode) =>
    apiFetch(`/medicines/${medicineId}/barcode`, { method: "PATCH", ...jsonBody({ barcode }) }),
  getLearningRules: () => apiFetch("/medicines/learning/rules"),
  deleteLearningRule: (ruleId) => apiFetch(`/medicines/learning/rules/${ruleId}`, { method: "DELETE" }),

  // --- Dashboard ---
  dashboardSummary: () => apiFetch("/dashboard/summary"),

  // --- Stock & Reorder ---
  getStockSummary: () => apiFetch("/stock/summary"),
  getStockSnapshot: (medicineId) => apiFetch(`/stock/medicine/${medicineId}/snapshot`),
  getStockLedger: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return apiFetch(`/stock/ledger${qs ? "?" + qs : ""}`);
  },
  recordSale: (medicineId, qtySold) =>
    apiFetch("/stock/sales", { method: "POST", ...jsonBody({ medicine_id: medicineId, qty_sold: qtySold }) }),
  recordAdjustment: (payload) =>
    apiFetch("/stock/adjustments", { method: "POST", ...jsonBody(payload) }),
  getReorderList: () => apiFetch("/stock/reorder-list"),
  addManualReorderItem: (payload) => apiFetch("/stock/reorder-list/manual", { method: "POST", ...jsonBody(payload) }),
  fulfillReorderItem: (id) => apiFetch(`/stock/reorder-list/${id}/fulfill`, { method: "PATCH" }),
  removeReorderItem: (id) => apiFetch(`/stock/reorder-list/${id}`, { method: "DELETE" }),
  updateLowStockThreshold: (medicineId, threshold) =>
    apiFetch(`/stock/medicine/${medicineId}/threshold`, { method: "PATCH", ...jsonBody({ low_stock_threshold: threshold }) }),
  getSmartReorderList: (windowDays = 30) => apiFetch(`/stock/smart-reorder?window_days=${windowDays}`),
  getSmartThreshold: (medicineId, windowDays = 30) => apiFetch(`/stock/medicine/${medicineId}/smart-threshold?window_days=${windowDays}`),
  applySmartThreshold: (medicineId) => apiFetch(`/stock/medicine/${medicineId}/smart-threshold/apply`, { method: "POST" }),
  updateLeadTime: (medicineId, leadTimeDays) =>
    apiFetch(`/stock/medicine/${medicineId}/lead-time`, { method: "PATCH", ...jsonBody({ lead_time_days: leadTimeDays }) }),


  // --- Expiry Tracking ---
  getExpiryDashboard: (days = 90) => apiFetch(`/expiry/dashboard?days=${days}`),
  getExpiryBatches: (days = 90) => apiFetch(`/expiry/dashboard?days=${typeof days === "object" ? days.days || 90 : days}`),
  getExpirySummary: () => apiFetch("/expiry/summary"),
  getMissingExpiry: () => apiFetch("/expiry/missing"),
  fillExpiry: (batchId, expiryDate) =>
    apiFetch(`/expiry/batch/${batchId}`, { method: "PATCH", ...jsonBody({ expiry_date: expiryDate }) }),
  updateExpiryBatch: (batchId, payload) =>
    apiFetch(`/expiry/batch/${batchId}`, { method: "PATCH", ...jsonBody(payload) }),

  // --- Analytics ---
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
  getTopHikes: (limit = 10) => apiFetch(`/analytics/top-hikes?limit=${limit}`),
  getInventoryValuation: () => apiFetch("/analytics/inventory-valuation"),
  getDeadStock: (days = 90) => apiFetch(`/analytics/dead-stock?days=${days}`),

  // --- GST Reports ---
  getGstReport: (year, month) => {
    const params = new URLSearchParams();
    if (year) params.set("year", year);
    if (month) params.set("month", month);
    return apiFetch(`/gst/summary?${params.toString()}`);
  },
};