import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { api } from "../api/client.js";

const METHOD_META = {
  holt_winters: { label: "Seasonal forecast (Holt-Winters)", badge: "auto" },
  flat_average: { label: "Flat average (limited history)", badge: "manual" },
  flat_average_fallback: { label: "Flat average (model fallback)", badge: "manual" },
  isolation_forest: { label: "IsolationForest", badge: "auto" },
  zscore_fallback: { label: "Statistical fallback (z-score)", badge: "manual" },
  none: { label: "No data yet", badge: "unmatched" },
};

function formatMoney(n) {
  if (n == null) return "—";
  return "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

// ---------------------------------------------------------------------------
// Tab 1: Demand Forecast
// ---------------------------------------------------------------------------
function ForecastTab() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [medicine, setMedicine] = useState(null);
  const [forecast, setForecast] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (query.trim().length < 2) { setResults([]); return; }
    const t = setTimeout(() => api.browseMedicines({ q: query, page: 1, page_size: 8 }).then((d) => setResults(d.items)), 250);
    return () => clearTimeout(t);
  }, [query]);

  function selectMedicine(m) {
    setMedicine(m);
    setQuery(""); setResults([]);
    setLoading(true);
    api.getDemandForecast(m.id, 14, 180).then(setForecast).finally(() => setLoading(false));
  }

  const meta = forecast ? (METHOD_META[forecast.method] || { label: forecast.method, badge: "manual" }) : null;

  return (
    <div>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>📈 Demand Forecast</h3>
        <p style={{ color: "#666", fontSize: 13 }}>
          A 14-day forecast per medicine — uses a seasonal model (Holt-Winters, weekly pattern)
          once there's enough sales history, and degrades honestly to a flat average otherwise
          rather than pretending to be confident with too little data.
        </p>
        <input
          style={{ width: "100%" }}
          placeholder="Search a medicine to forecast..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        {results.length > 0 && (
          <table style={{ marginTop: 8 }}>
            <tbody>
              {results.map((m) => (
                <tr key={m.id} style={{ cursor: "pointer" }} onClick={() => selectMedicine(m)}>
                  <td>{m.particulars}</td>
                  <td style={{ color: "#888" }}>{m.unit}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {loading && <p style={{ color: "#888", fontSize: 13 }}>Computing forecast...</p>}

      {!loading && forecast && (
        <div className="card">
          <div className="flex-between">
            <h3 style={{ margin: 0 }}>{forecast.medicine_name}</h3>
            <span className={`badge ${meta.badge}`}>{meta.label}</span>
          </div>
          {forecast.reason && <p style={{ color: "#92400e", fontSize: 12.5, background: "#fef3c7", padding: "8px 12px", borderRadius: 8, marginTop: 10 }}>{forecast.reason}</p>}

          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={forecast.forecast}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="date" fontSize={11} tickFormatter={(d) => d.slice(5)} />
              <YAxis fontSize={11} />
              <Tooltip />
              <Line type="monotone" dataKey="predicted_qty" stroke="#2563eb" strokeWidth={2} dot />
            </LineChart>
          </ResponsiveContainer>
          <p style={{ fontSize: 12, color: "#888", marginTop: 6 }}>
            Based on {forecast.history_days_used} days of history. Predicted units/day for the next {forecast.forecast.length} days.
          </p>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Explain-with-AI button, shared by both anomaly tables below
// ---------------------------------------------------------------------------
function ExplainButton({ anomaly }) {
  const [explanation, setExplanation] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleExplain() {
    setLoading(true);
    try {
      const res = await api.explainAnomaly(anomaly);
      setExplanation(res.explanation);
    } finally {
      setLoading(false);
    }
  }

  if (explanation) {
    return <div className="anomaly-explanation">{explanation}</div>;
  }
  return (
    <button className="secondary anomaly-explain-btn" onClick={handleExplain} disabled={loading}>
      {loading ? "Thinking..." : "🤖 Explain with AI"}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Tab 2: Anomaly Detection
// ---------------------------------------------------------------------------
function AnomalyTab() {
  const [priceJumps, setPriceJumps] = useState(null);
  const [stockAdj, setStockAdj] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.getPriceJumpAnomalies(180), api.getStockAdjustmentAnomalies(90)])
      .then(([p, s]) => { setPriceJumps(p); setStockAdj(s); })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p style={{ color: "#888", fontSize: 13 }}>Scanning for anomalies...</p>;

  return (
    <div>
      <div className="card">
        <div className="flex-between">
          <h3 style={{ margin: 0 }}>💹 Unusual price changes</h3>
          <span className={`badge ${(METHOD_META[priceJumps.method] || {}).badge || "manual"}`}>
            {(METHOD_META[priceJumps.method] || {}).label || priceJumps.method}
          </span>
        </div>
        {!priceJumps.has_sufficient_data && (
          <p style={{ fontSize: 12, color: "#888", marginTop: 6 }}>
            Only {priceJumps.sample_size} rate change(s) recorded — using a simpler statistical
            check until there's more history for IsolationForest to be meaningful.
          </p>
        )}
        {priceJumps.anomalies.length === 0 ? (
          <p style={{ color: "#888", fontSize: 13, marginTop: 10 }}>Nothing unusual flagged in this window.</p>
        ) : (
          priceJumps.anomalies.map((a) => (
            <div key={a.rate_history_id} className="anomaly-row">
              <div className="flex-between">
                <div>
                  <strong>{a.medicine_name}</strong>
                  <div style={{ fontSize: 12.5, color: "#666" }}>
                    {formatMoney(a.old_rate)} → {formatMoney(a.new_rate)} · {new Date(a.changed_at).toLocaleDateString()}
                  </div>
                </div>
                <span className={`badge ${a.pct_change >= 0 ? "unmatched" : "manual"}`}>{a.pct_change >= 0 ? "▲" : "▼"} {Math.abs(a.pct_change)}%</span>
              </div>
              <ExplainButton anomaly={a} />
            </div>
          ))
        )}
      </div>

      <div className="card">
        <div className="flex-between">
          <h3 style={{ margin: 0 }}>⚖️ Unusual stock adjustments</h3>
          <span className={`badge ${(METHOD_META[stockAdj.method] || {}).badge || "manual"}`}>
            {(METHOD_META[stockAdj.method] || {}).label || stockAdj.method}
          </span>
        </div>
        {stockAdj.unattributed_count > 0 && (
          <p style={{ fontSize: 12, color: "#888", marginTop: 6 }}>
            {stockAdj.unattributed_count} adjustment(s) in this window have no staff account attached (recorded before this tracking existed) and are excluded from the staff breakdown below.
          </p>
        )}

        {stockAdj.flagged_adjustments.length === 0 ? (
          <p style={{ color: "#888", fontSize: 13, marginTop: 10 }}>No individually unusual adjustments flagged.</p>
        ) : (
          stockAdj.flagged_adjustments.map((a) => (
            <div key={a.stock_ledger_id} className="anomaly-row">
              <div className="flex-between">
                <div>
                  <strong>{a.medicine_name}</strong>
                  <div style={{ fontSize: 12.5, color: "#666" }}>
                    {a.change_qty > 0 ? "+" : ""}{a.change_qty} units · {a.created_by_username || "Unattributed"} · {new Date(a.created_at).toLocaleDateString()}
                  </div>
                  {a.note && <div style={{ fontSize: 12, color: "#888", marginTop: 2 }}>{a.note}</div>}
                </div>
              </div>
              <ExplainButton anomaly={a} />
            </div>
          ))
        )}

        {stockAdj.staff_summary.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <h4 style={{ marginBottom: 8 }}>Adjustment share by staff account</h4>
            {stockAdj.staff_summary.map((s) => (
              <div key={s.user_id} className="reorder-item-row">
                <div>
                  <div className="reorder-item-name">{s.username}</div>
                  <div className="reorder-item-meta">{s.adjustment_count} adjustment(s) · {s.share_pct}% of total</div>
                </div>
                {s.is_over_represented && <span className="badge unmatched">Worth a look</span>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default function Predictive() {
  const [tab, setTab] = useState("forecast");

  return (
    <div>
      <div className="card">
        <h2 style={{ marginBottom: 4 }}>🔮 Predictive Intelligence</h2>
        <p style={{ color: "#666", fontSize: 13, marginTop: 0 }}>
          Demand forecasting beyond a flat average, and statistically unusual patterns worth a
          look — never an accusation, always a prompt to double-check.
        </p>
        <div className="tabs" style={{ marginBottom: 0 }}>
          <button className={`tab-button ${tab === "forecast" ? "active" : ""}`} onClick={() => setTab("forecast")}>Demand Forecast</button>
          <button className={`tab-button ${tab === "anomalies" ? "active" : ""}`} onClick={() => setTab("anomalies")}>Anomaly Detection</button>
        </div>
      </div>

      {tab === "forecast" && <ForecastTab />}
      {tab === "anomalies" && <AnomalyTab />}

      <style>{`
        .anomaly-row { border-bottom: 1px solid #f0f0f0; padding: 12px 4px; }
        .anomaly-row:last-child { border-bottom: none; }
        .anomaly-explain-btn { margin-top: 8px; font-size: 12px; padding: 6px 12px; }
        .anomaly-explanation {
          margin-top: 8px; background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 8px;
          padding: 10px 12px; font-size: 12.5px; color: #0369a1; line-height: 1.5;
        }
      `}</style>
    </div>
  );
}