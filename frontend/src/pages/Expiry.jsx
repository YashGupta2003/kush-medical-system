import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { AlertTriangle, Clock, Calendar, AlertOctagon, CheckCircle, Save } from "lucide-react";
import { api } from "../api/client.js";
import EmptyState from "../components/EmptyState.jsx";

const URGENCY_META = {
  expired: { label: "Expired", color: "var(--danger-600)", bg: "var(--danger-100)", icon: <AlertOctagon size={18} /> },
  critical: { label: "Critical — 7 days or less", color: "var(--warning-700)", bg: "var(--warning-100)", icon: <AlertTriangle size={18} /> },
  warning: { label: "Expiring soon — 30 days or less", color: "var(--warning-600)", bg: "var(--warning-50)", icon: <Clock size={18} /> },
  upcoming: { label: "Upcoming", color: "var(--primary-600)", bg: "var(--primary-50)", icon: <Calendar size={18} /> },
};

function MissingExpiryPrompt({ items, onFilled }) {
  const [dates, setDates] = useState({});
  const [saving, setSaving] = useState({});

  async function handleSave(batchId) {
    const value = dates[batchId];
    if (!value) return;
    setSaving((s) => ({ ...s, [batchId]: true }));
    try {
      await api.fillExpiry(batchId, value);
      onFilled();
    } finally {
      setSaving((s) => ({ ...s, [batchId]: false }));
    }
  }

  if (items.length === 0) return null;

  return (
    <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="card" style={{ borderLeft: "4px solid var(--warning-500)", marginBottom: "20px" }}>
      <div className="flex-between">
        <h3 style={{ margin: 0, display: "flex", alignItems: "center", gap: "8px", color: "var(--text-main)" }}>
          <AlertTriangle size={20} color="var(--warning-600)" /> Expiry date missing for {items.length} item{items.length === 1 ? "" : "s"}
        </h3>
      </div>
      <p style={{ color: "var(--text-secondary)", fontSize: "13px", lineHeight: 1.5, marginTop: "8px" }}>
        These arrived on a confirmed bill, but the expiry date couldn't be read from the photo.
        Please check the packet and enter it here so they show up on the tracker above.
      </p>
      <div style={{ marginTop: "16px", display: "flex", flexDirection: "column", gap: "12px" }}>
        {items.map((item) => (
          <div key={item.batch_id} className="reorder-item-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px", background: "var(--bg-muted)", padding: "12px", borderRadius: "8px" }}>
            <div style={{ flex: 1, minWidth: "200px" }}>
              <div className="reorder-item-name" style={{ fontWeight: 600, color: "var(--text-main)", marginBottom: "4px" }}>{item.medicine_name}</div>
              <div className="reorder-item-meta" style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
                {item.batch_no && <>Batch: <strong style={{ color: "var(--text-main)" }}>{item.batch_no}</strong> · </>}
                Qty: {item.qty_received} · From: {item.distributor_name || "unknown distributor"}
              </div>
            </div>
            <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
              <input
                type="date"
                style={{ padding: "8px", border: "1px solid var(--border-color)", borderRadius: "6px" }}
                value={dates[item.batch_id] || ""}
                onChange={(e) => setDates((d) => ({ ...d, [item.batch_id]: e.target.value }))}
              />
              <button
                className="btn btn-primary"
                disabled={!dates[item.batch_id] || saving[item.batch_id]}
                onClick={() => handleSave(item.batch_id)}
                style={{ display: "flex", alignItems: "center", gap: "6px", padding: "8px 16px" }}
              >
                <Save size={16} /> {saving[item.batch_id] ? "Saving..." : "Save"}
              </button>
            </div>
          </div>
        ))}
      </div>
    </motion.div>
  );
}

export default function Expiry() {
  const [days, setDays] = useState(30);
  const [batches, setBatches] = useState([]);
  const [summary, setSummary] = useState(null);
  const [missing, setMissing] = useState([]);
  const [loading, setLoading] = useState(true);

  function refresh() {
    Promise.all([
      api.getExpiryDashboard(days),
      api.getExpirySummary(),
      api.getMissingExpiry(),
    ]).then(([b, s, m]) => {
      setBatches(b);
      setSummary(s);
      setMissing(m);
      setLoading(false);
    });
  }

  useEffect(() => { refresh(); /* eslint-disable-next-line */ }, [days]);

  const grouped = { expired: [], critical: [], warning: [], upcoming: [] };
  batches.forEach((b) => grouped[b.urgency]?.push(b));

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }} className="page-content">
      <div className="card" style={{ marginBottom: "20px" }}>
        <div style={{ display: "flex", gap: "12px", alignItems: "flex-start", marginBottom: "20px" }}>
          <div style={{ background: "var(--primary-100)", padding: "10px", borderRadius: "10px" }}>
            <Calendar size={24} color="var(--primary-600)" />
          </div>
          <div>
            <h2 style={{ margin: "0 0 4px 0", color: "var(--text-main)" }}>Expiry Tracker</h2>
            <p style={{ color: "var(--text-secondary)", fontSize: "13px", margin: 0, lineHeight: 1.5 }}>
              Every batch that's expired or expiring soon, so nothing sits on the shelf past its date.
            </p>
          </div>
        </div>

        {summary && (
          <div className="stat-row" style={{ marginBottom: "20px" }}>
            <div className="stat-box warn" style={{ background: "var(--danger-50)", borderColor: "var(--danger-200)" }}>
              <div className="value" style={{ color: "var(--danger-700)" }}>{summary.expired}</div>
              <div className="label" style={{ color: "var(--danger-600)" }}>Already expired</div>
            </div>
            <div className="stat-box warn" style={{ background: "var(--warning-50)", borderColor: "var(--warning-300)" }}>
              <div className="value" style={{ color: "var(--warning-700)" }}>{summary.critical}</div>
              <div className="label" style={{ color: "var(--warning-700)" }}>Expiring ≤ 7 days</div>
            </div>
            <div className="stat-box">
              <div className="value">{summary.warning}</div>
              <div className="label">Expiring ≤ 30 days</div>
            </div>
            <div className="stat-box" style={{ background: summary.missing_expiry > 0 ? "var(--warning-50)" : "var(--bg-surface)" }}>
              <div className="value">{summary.missing_expiry}</div>
              <div className="label">Missing expiry info</div>
            </div>
          </div>
        )}

        <div style={{ display: "flex", gap: "8px", overflowX: "auto", paddingBottom: "4px" }}>
          {[7, 30, 90].map((d) => (
            <button key={d} className={`btn ${days === d ? "btn-primary" : "secondary"}`} onClick={() => setDays(d)} style={{ padding: "8px 16px", whiteSpace: "nowrap" }}>
              Next {d} days
            </button>
          ))}
        </div>
      </div>

      <MissingExpiryPrompt items={missing} onFilled={refresh} />

      {loading && <p style={{ color: "var(--text-muted)", padding: "20px", textAlign: "center" }}>Loading...</p>}

      {!loading && Object.keys(grouped).every(k => grouped[k].length === 0) && (
        <EmptyState 
          icon={CheckCircle}
          title="All clear! No medicines are expiring soon."
          message="Your inventory is perfectly healthy. No batches are nearing expiration in this window."
        />
      )}

      {["expired", "critical", "warning", "upcoming"].map((urgencyKey) => {
        const items = grouped[urgencyKey];
        if (!items || items.length === 0) return null;
        const meta = URGENCY_META[urgencyKey];
        return (
          <div className="card" key={urgencyKey} style={{ borderLeft: `4px solid ${meta.color}`, marginBottom: "16px", overflow: "hidden", padding: "20px" }}>
            <h3 style={{ color: meta.color, marginTop: 0, display: "flex", alignItems: "center", gap: "8px", marginBottom: "16px" }}>
              {meta.icon} {meta.label} ({items.length})
            </h3>
            <div style={{ overflowX: "auto" }}>
              <table className="table" style={{ width: "100%", margin: 0 }}>
                <thead style={{ background: meta.bg }}>
                  <tr>
                    <th style={{ padding: "12px", textAlign: "left", color: meta.color }}>Medicine</th>
                    <th style={{ padding: "12px", textAlign: "left", color: meta.color }}>Batch</th>
                    <th style={{ padding: "12px", textAlign: "right", color: meta.color }}>Qty</th>
                    <th style={{ padding: "12px", textAlign: "left", color: meta.color }}>Distributor</th>
                    <th style={{ padding: "12px", textAlign: "left", color: meta.color }}>Expiry date</th>
                    <th style={{ padding: "12px", textAlign: "right", color: meta.color }}>Days left</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((b) => (
                    <tr key={b.batch_id} style={{ transition: "background 0.2s" }} className="hover-row">
                      <td style={{ padding: "12px", borderBottom: "1px solid var(--border-color)" }}>
                        <strong style={{ color: "var(--text-main)" }}>{b.medicine_name}</strong>
                      </td>
                      <td style={{ padding: "12px", borderBottom: "1px solid var(--border-color)", color: "var(--text-secondary)" }}>{b.batch_no || "—"}</td>
                      <td style={{ padding: "12px", borderBottom: "1px solid var(--border-color)", textAlign: "right", fontWeight: 500, color: "var(--text-main)" }}>{b.qty_received}</td>
                      <td style={{ padding: "12px", borderBottom: "1px solid var(--border-color)", color: "var(--text-secondary)", fontSize: "13px" }}>{b.distributor_name || "—"}</td>
                      <td style={{ padding: "12px", borderBottom: "1px solid var(--border-color)" }}>{new Date(b.expiry_date).toLocaleDateString(undefined, { month: 'short', year: 'numeric' })}</td>
                      <td style={{ padding: "12px", borderBottom: "1px solid var(--border-color)", textAlign: "right", color: meta.color, fontWeight: 600 }}>
                        {b.days_remaining < 0 ? `${Math.abs(b.days_remaining)} days ago` : `${b.days_remaining} days`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        );
      })}
      <style>{`.hover-row:hover { background: var(--bg-muted) !important; }`}</style>
    </motion.div>
  );
}