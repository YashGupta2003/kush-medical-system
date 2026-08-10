import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { List, Filter, ChevronLeft, ChevronRight, FileText } from "lucide-react";
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
    { key: "needs_attention", color: "var(--danger-500)" },
    { key: "queued", color: "var(--text-muted)" },
    { key: "processing", color: "var(--warning-500)" },
    { key: "pending_review", color: "var(--primary-500)" },
    { key: "confirmed", color: "var(--success-500)" },
    { key: "failed", color: "var(--danger-700)" },
  ];
  return (
    <div>
      <div style={{ display: "flex", height: "14px", borderRadius: "7px", overflow: "hidden", background: "var(--bg-muted)" }}>
        {segments.map((s) => (
          counts[s.key] > 0 && (
            <div key={s.key} style={{ width: `${(counts[s.key] / total) * 100}%`, background: s.color, transition: "width 0.3s ease" }} title={`${s.key}: ${counts[s.key]}`} />
          )
        ))}
      </div>
      <div style={{ display: "flex", gap: "16px", flexWrap: "wrap", marginTop: "12px", fontSize: "13px" }}>
        {segments.map((s) => (
          <span key={s.key} style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--text-secondary)" }}>
            <span style={{ width: "10px", height: "10px", borderRadius: "50%", background: s.color, display: "inline-block" }} />
            {STATUS_META[s.key].label}: <strong style={{ color: "var(--text-main)" }}>{counts[s.key] || 0}</strong>
          </span>
        ))}
      </div>
    </div>
  );
}

export default function BillHistory() {
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
      if (data && Array.isArray(data.items)) {
        setBills(data.items);
        setTotal(data.total);
      } else if (Array.isArray(data)) {
        setBills(data);
        setTotal(data.length);
      }
    });
  }

  useEffect(() => {
    setPage(1);
  }, [filterStatus]);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 4000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterStatus, page]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.2 }}
      className="page-content"
    >
      <div className="card">
        <div style={{ display: "flex", alignItems: "flex-start", gap: "12px", marginBottom: "16px" }}>
          <div style={{ background: "var(--primary-100)", padding: "10px", borderRadius: "10px" }}>
            <List size={24} color="var(--primary-600)" />
          </div>
          <div style={{ flex: 1 }}>
            <h2 style={{ margin: "0 0 12px 0", color: "var(--text-main)" }}>Review queue</h2>
            {summary && <ProgressBar counts={summary.bill_status_counts} />}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="flex-between" style={{ marginBottom: "16px" }}>
          <h3 style={{ margin: 0, color: "var(--text-main)", display: "flex", alignItems: "center", gap: "8px" }}>
            <FileText size={18} color="var(--text-muted)" /> All bills <span style={{ fontWeight: 400, fontSize: "13px", color: "var(--text-muted)" }}>({total} total)</span>
          </h3>
          <div style={{ position: "relative" }}>
            <Filter size={16} style={{ position: "absolute", left: "10px", top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }} />
            <select style={{ paddingLeft: "32px", paddingRight: "28px" }} value={filterStatus || ""} onChange={(e) => setFilterStatus(e.target.value || null)}>
              <option value="">All statuses</option>
              {Object.entries(STATUS_META).map(([key, meta]) => (
                <option key={key} value={key}>{meta.label}</option>
              ))}
            </select>
          </div>
        </div>
        
        <div style={{ overflowX: "auto" }}>
          <table className="table" style={{ width: "100%", margin: 0 }}>
            <thead>
              <tr>
                <th style={{ padding: "12px" }}>Date</th>
                <th style={{ padding: "12px" }}>Distributor</th>
                <th style={{ padding: "12px" }}>Invoice no.</th>
                <th style={{ padding: "12px" }}>Total</th>
                <th style={{ padding: "12px" }}>Status</th>
                <th style={{ padding: "12px" }}></th>
              </tr>
            </thead>
            <tbody>
              {bills.map((b) => {
                const meta = STATUS_META[b.status] || { label: b.status, badge: "manual" };
                return (
                  <tr key={b.id} className="hover-row" style={{ transition: "background 0.2s ease" }}>
                    <td style={{ padding: "12px", borderBottom: "1px solid var(--border-color)", whiteSpace: "nowrap" }}>{b.year}-{String(b.month).padStart(2, "0")}</td>
                    <td style={{ padding: "12px", borderBottom: "1px solid var(--border-color)" }}>{b.distributor_name || "—"}</td>
                    <td style={{ padding: "12px", borderBottom: "1px solid var(--border-color)" }}>{b.invoice_no || "—"}</td>
                    <td style={{ padding: "12px", borderBottom: "1px solid var(--border-color)" }}>{b.total_amount}</td>
                    <td style={{ padding: "12px", borderBottom: "1px solid var(--border-color)" }}><span className={`badge ${meta.badge}`}>{meta.label}</span></td>
                    <td style={{ padding: "12px", borderBottom: "1px solid var(--border-color)", textAlign: "right" }}>
                      {(b.status === "pending_review" || b.status === "needs_attention") && (
                        <Link to={`/review/${b.id}`} className="btn btn-primary" style={{ padding: "6px 12px", fontSize: "13px", display: "inline-block" }}>Review</Link>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {totalPages > 1 && (
          <div style={{ display: "flex", gap: "12px", marginTop: "16px", alignItems: "center", justifyContent: "center" }}>
            <button
              className="btn secondary"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              style={{ display: "flex", alignItems: "center", gap: "4px" }}
            >
              <ChevronLeft size={16} /> Previous
            </button>
            <span style={{ fontSize: "14px", color: "var(--text-secondary)", fontWeight: 500 }}>
              Page {page} of {totalPages}
            </span>
            <button
              className="btn secondary"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              style={{ display: "flex", alignItems: "center", gap: "4px" }}
            >
              Next <ChevronRight size={16} />
            </button>
          </div>
        )}
      </div>
      <style>{`
        .hover-row:hover { background: var(--bg-muted); }
      `}</style>
    </motion.div>
  );
}
