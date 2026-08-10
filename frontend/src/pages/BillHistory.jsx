import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";

const STATUS_META = {
  queued: { label: "Queued", badge: "manual" },
  processing: { label: "Processing", badge: "manual" },
  pending_review: { label: "Ready for review", badge: "auto" },
  needs_attention: { label: "Needs attention", badge: "unmatched" },
  confirmed: { label: "Confirmed", badge: "auto" },
  failed: { label: "Failed", badge: "unmatched" },
};

const PAGE_SIZE = 50;

function ProgressBar({ counts }) {
  const total = Object.values(counts).reduce((a, b) => a + b, 0) || 1;
  const segments = [
    { key: "needs_attention", color: "#dc2626" },
    { key: "queued", color: "#9ca3af" },
    { key: "processing", color: "#f59e0b" },
    { key: "pending_review", color: "#3b82f6" },
    { key: "confirmed", color: "#16a34a" },
    { key: "failed", color: "#7f1d1d" },
  ];
  return (
    <div>
      <div style={{ display: "flex", height: 14, borderRadius: 7, overflow: "hidden", background: "#eee" }}>
        {segments.map((s) => (
          counts[s.key] > 0 && (
            <div key={s.key} style={{ width: `${(counts[s.key] / total) * 100}%`, background: s.color }} title={`${s.key}: ${counts[s.key]}`} />
          )
        ))}
      </div>
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginTop: 10, fontSize: 13 }}>
        {segments.map((s) => (
          <span key={s.key} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ width: 10, height: 10, borderRadius: 5, background: s.color, display: "inline-block" }} />
            {STATUS_META[s.key].label}: <strong>{counts[s.key] || 0}</strong>
          </span>
        ))}
      </div>
    </div>
  );
}

export default function BillHistory() {
  // BUG FIX #2 (frontend): Use paginated state instead of a flat bills array.
  // The old code fetched ALL bills in one API call which would cause OOM on the
  // server once production data accumulated. Now we fetch in pages of PAGE_SIZE.
  const [bills, setBills] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [summary, setSummary] = useState(null);
  const [filterStatus, setFilterStatus] = useState(null);

  const offset = (page - 1) * PAGE_SIZE;
  const totalPages = Math.ceil(total / PAGE_SIZE) || 1;

  function refresh() {
    api.dashboardSummary().then(setSummary);
    const params = { limit: PAGE_SIZE, offset };
    if (filterStatus) params.status = filterStatus;
    api.listBills(params).then((data) => {
      // Handle paginated response: { items, total, limit, offset }
      if (data && Array.isArray(data.items)) {
        setBills(data.items);
        setTotal(data.total);
      } else if (Array.isArray(data)) {
        // Fallback: handle legacy non-paginated response gracefully
        setBills(data);
        setTotal(data.length);
      }
    });
  }

  // Reset to page 1 when filter changes
  useEffect(() => {
    setPage(1);
  }, [filterStatus]);

  useEffect(() => {
    refresh();
    // Only auto-refresh if there are bills in non-terminal states
    const interval = setInterval(refresh, 4000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterStatus, page]);

  return (
    <div>
      <div className="card">
        <h2>Review queue</h2>
        {summary && <ProgressBar counts={summary.bill_status_counts} />}
      </div>

      <div className="card">
        <div className="flex-between">
          <h3 style={{ margin: 0 }}>All bills <span style={{ fontWeight: 400, fontSize: 13, color: "#666" }}>({total} total)</span></h3>
          <select value={filterStatus || ""} onChange={(e) => setFilterStatus(e.target.value || null)}>
            <option value="">All statuses</option>
            {Object.entries(STATUS_META).map(([key, meta]) => (
              <option key={key} value={key}>{meta.label}</option>
            ))}
          </select>
        </div>
        <table>
          <thead>
            <tr><th>Date</th><th>Distributor</th><th>Invoice no.</th><th>Total</th><th>Status</th><th></th></tr>
          </thead>
          <tbody>
            {bills.map((b) => {
              const meta = STATUS_META[b.status] || { label: b.status, badge: "manual" };
              return (
                <tr key={b.id}>
                  <td>{b.year}-{String(b.month).padStart(2, "0")}</td>
                  <td>{b.distributor_name || "—"}</td>
                  <td>{b.invoice_no || "—"}</td>
                  <td>{b.total_amount}</td>
                  <td><span className={`badge ${meta.badge}`}>{meta.label}</span></td>
                  <td>
                    {(b.status === "pending_review" || b.status === "needs_attention") && (
                      <Link to={`/review/${b.id}`}>Review</Link>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {/* BUG FIX #2: Pagination controls */}
        {totalPages > 1 && (
          <div style={{ display: "flex", gap: 8, marginTop: 12, alignItems: "center" }}>
            <button
              className="secondary"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
            >
              ← Previous
            </button>
            <span style={{ fontSize: 13, color: "#666" }}>
              Page {page} of {totalPages}
            </span>
            <button
              className="secondary"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
            >
              Next →
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
