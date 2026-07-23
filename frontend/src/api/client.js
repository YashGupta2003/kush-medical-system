const BASE = "/api";

async function handle(res) {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

export const api = {
  uploadBill: (formData) =>
    fetch(`${BASE}/bills/upload`, { method: "POST", body: formData }).then(handle),

  uploadBillsBatch: (formData) =>
    fetch(`${BASE}/bills/upload-batch`, { method: "POST", body: formData }).then(handle),

  getBillStatus: (id) => fetch(`${BASE}/bills/${id}/status`).then(handle),

  getBill: (id) => fetch(`${BASE}/bills/${id}`).then(handle),

  getBillImageUrl: (id) => `${BASE}/bills/${id}/image`,

  listBills: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return fetch(`${BASE}/bills${qs ? "?" + qs : ""}`).then(handle);
  },

  confirmBill: (payload) =>
    fetch(`${BASE}/bills/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then(handle),

  reprocessRegion: (billId, box) =>
    fetch(`${BASE}/bills/${billId}/reprocess-region`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(box),
    }).then(handle),

  browseMedicines: ({ q = "", page = 1, page_size = 50 } = {}) => {
    const params = new URLSearchParams({ page, page_size });
    if (q) params.set("q", q);
    return fetch(`${BASE}/medicines?${params.toString()}`).then(handle);
  },

  getMedicineHistory: (id) => fetch(`${BASE}/medicines/${id}/history`).then(handle),

  dashboardSummary: () => fetch(`${BASE}/dashboard/summary`).then(handle),

  getStockSnapshot: (medicineId) => fetch(`${BASE}/stock/medicine/${medicineId}/snapshot`).then(handle),

  recordSale: (medicineId, qtySold) =>
    fetch(`${BASE}/stock/sales`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ medicine_id: medicineId, qty_sold: qtySold }),
    }).then(handle),

  getReorderList: () => fetch(`${BASE}/stock/reorder-list`).then(handle),

  addManualReorderItem: (payload) =>
    fetch(`${BASE}/stock/reorder-list/manual`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then(handle),

  removeReorderItem: (id) =>
    fetch(`${BASE}/stock/reorder-list/${id}`, { method: "DELETE" }).then(handle),

  updateLowStockThreshold: (medicineId, threshold) =>
    fetch(`${BASE}/stock/medicine/${medicineId}/threshold`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ low_stock_threshold: threshold }),
    }).then(handle),
};
