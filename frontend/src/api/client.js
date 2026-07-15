// All requests go through /api, proxied to the FastAPI backend (see vite.config.js).
// Change this if you deploy the backend somewhere other than localhost:8000.
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

  getBill: (id) => fetch(`${BASE}/bills/${id}`).then(handle),

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

  searchMedicines: (q) =>
    fetch(`${BASE}/medicines/search?q=${encodeURIComponent(q)}`).then(handle),

  getMedicineHistory: (id) => fetch(`${BASE}/medicines/${id}/history`).then(handle),

  dashboardSummary: () => fetch(`${BASE}/dashboard/summary`).then(handle),
};
