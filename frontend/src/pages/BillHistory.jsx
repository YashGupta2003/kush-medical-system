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
  const [bills, setBills] = useState([]);
  const [summary, setSummary] = useState(null);
  const [filterStatus, setFilterStatus] = useState(null);

  function refresh() {
    api.dashboardSummary().then(setSummary);
    api.listBills(filterStatus ? { status: filterStatus } : {}).then(setBills);
  }

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 4000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterStatus]);

  return (
    <div>
      <div className="card">
        <h2>Review queue</h2>
        {summary && <ProgressBar counts={summary.bill_status_counts} />}
      </div>

      <div className="card">
        <div className="flex-between">
          <h3 style={{ margin: 0 }}>All bills</h3>
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
      </div>
    </div>
  );
}
