import { useEffect, useState } from "react";
import { api } from "../api/client.js";

const URGENCY_META = {
  expired: { label: "Expired", color: "#dc2626", bg: "#fee2e2", icon: "⛔" },
  critical: { label: "Critical — 7 days or less", color: "#ea580c", bg: "#ffedd5", icon: "🔥" },
  warning: { label: "Expiring soon — 30 days or less", color: "#ca8a04", bg: "#fef3c7", icon: "⚠️" },
  upcoming: { label: "Upcoming", color: "#0284c7", bg: "#e0f2fe", icon: "📅" },
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
    <div className="card" style={{ borderLeft: "4px solid #ea580c" }}>
      <div className="flex-between">
        <h3 style={{ margin: 0 }}>📝 Expiry date missing for {items.length} item{items.length === 1 ? "" : "s"}</h3>
      </div>
      <p style={{ color: "#666", fontSize: 13 }}>
        These arrived on a confirmed bill, but the expiry date couldn't be read from the photo.
        Please check the packet and enter it here so they show up on the tracker above.
      </p>
      {items.map((item) => (
        <div key={item.batch_id} className="reorder-item-row">
          <div>
            <div className="reorder-item-name">{item.medicine_name}</div>
            <div className="reorder-item-meta">
              {item.batch_no && <>Batch: {item.batch_no} · </>}
              Qty: {item.qty_received} · From: {item.distributor_name || "unknown distributor"}
            </div>
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            <input
              type="date"
              value={dates[item.batch_id] || ""}
              onChange={(e) => setDates((d) => ({ ...d, [item.batch_id]: e.target.value }))}
            />
            <button
              disabled={!dates[item.batch_id] || saving[item.batch_id]}
              onClick={() => handleSave(item.batch_id)}
            >
              {saving[item.batch_id] ? "Saving..." : "Save"}
            </button>
          </div>
        </div>
      ))}
    </div>
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
    <div>
      <div className="card">
        <h2 style={{ marginBottom: 4 }}>⏳ Expiry Tracker</h2>
        <p style={{ color: "#666", fontSize: 13, marginTop: 0 }}>
          Every batch that's expired or expiring soon, so nothing sits on the shelf past its date.
        </p>

        {summary && (
          <div className="stat-row">
            <div className="stat-box warn"><div className="value">{summary.expired}</div><div className="label">Already expired</div></div>
            <div className="stat-box warn"><div className="value">{summary.critical}</div><div className="label">Expiring ≤ 7 days</div></div>
            <div className="stat-box"><div className="value">{summary.warning}</div><div className="label">Expiring ≤ 30 days</div></div>
            <div className="stat-box"><div className="value">{summary.missing_expiry}</div><div className="label">Missing expiry info</div></div>
          </div>
        )}

        <div style={{ display: "flex", gap: 8 }}>
          {[7, 30, 90].map((d) => (
            <button key={d} className={days === d ? "" : "secondary"} onClick={() => setDays(d)}>
              Next {d} days
            </button>
          ))}
        </div>
      </div>

      <MissingExpiryPrompt items={missing} onFilled={refresh} />

      {loading && <p>Loading...</p>}

      {!loading && batches.length === 0 && (
        <div className="card"><p style={{ color: "#666" }}>Nothing expiring in this window. 🎉</p></div>
      )}

      {["expired", "critical", "warning", "upcoming"].map((urgencyKey) => {
        const items = grouped[urgencyKey];
        if (!items || items.length === 0) return null;
        const meta = URGENCY_META[urgencyKey];
        return (
          <div className="card" key={urgencyKey} style={{ borderLeft: `4px solid ${meta.color}` }}>
            <h3 style={{ color: meta.color, marginTop: 0 }}>{meta.icon} {meta.label} ({items.length})</h3>
            <table>
              <thead>
                <tr><th>Medicine</th><th>Batch</th><th>Qty</th><th>Distributor</th><th>Expiry date</th><th>Days left</th></tr>
              </thead>
              <tbody>
                {items.map((b) => (
                  <tr key={b.batch_id}>
                    <td>{b.medicine_name}</td>
                    <td>{b.batch_no || "—"}</td>
                    <td>{b.qty_received}</td>
                    <td>{b.distributor_name || "—"}</td>
                    <td>{new Date(b.expiry_date).toLocaleDateString()}</td>
                    <td style={{ color: meta.color, fontWeight: 600 }}>
                      {b.days_remaining < 0 ? `${Math.abs(b.days_remaining)} days ago` : `${b.days_remaining} days`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })}
    </div>
  );
}