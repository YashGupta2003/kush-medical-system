import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { api } from "../api/client.js";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Lightbulb, BrainCircuit, Activity, TrendingUp, TrendingDown, 
  Search, ShieldAlert, Sparkles, HelpCircle, Package, ArrowUpRight, ArrowDownRight, ArrowRight
} from "lucide-react";

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
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
      <div className="card" style={{ marginBottom: "var(--space-6)" }}>
        <h3 style={{ marginTop: 0, display: "flex", alignItems: "center", gap: 8, fontSize: "var(--text-lg)" }}>
          <TrendingUp size={20} color="var(--primary-600)" /> Predictive Demand Modeling
        </h3>
        <p style={{ color: "var(--text-muted)", fontSize: "var(--text-sm)", marginBottom: "var(--space-4)" }}>
          Engineered to project 14-day demand. Employs Holt-Winters seasonal analysis when robust data is available, automatically degrading gracefully to flat-averaging for low-signal assets.
        </p>
        
        <div style={{ position: "relative" }}>
          <div style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }}>
            <Search size={16} />
          </div>
          <input
            className="input"
            style={{ width: "100%", paddingLeft: 36, fontSize: "var(--text-base)" }}
            placeholder="Search master directory to compute forecast..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        
        {results.length > 0 && (
          <div className="table-container" style={{ marginTop: "var(--space-2)", borderRadius: "var(--radius-md)" }}>
            <table className="table">
              <tbody>
                {results.map((m) => (
                  <tr key={m.id} style={{ cursor: "pointer" }} onClick={() => selectMedicine(m)}>
                    <td style={{ fontWeight: 500 }}>{m.particulars}</td>
                    <td style={{ color: "var(--text-muted)", textAlign: "right" }}>{m.unit}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {loading && (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "var(--space-8)" }}>
          <div className="skeleton" style={{ width: 48, height: 48, borderRadius: "50%", marginBottom: "var(--space-4)" }}></div>
          <p style={{ color: "var(--text-muted)", fontWeight: 500 }}>Running statistical models...</p>
        </div>
      )}

      {!loading && forecast && (
        <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} className="card card-raised" style={{ borderTop: "4px solid var(--primary-500)" }}>
          <div className="flex-between" style={{ marginBottom: "var(--space-4)" }}>
            <div>
              <h3 style={{ margin: 0, fontSize: "var(--text-xl)" }}>{forecast.medicine_name}</h3>
              <p style={{ margin: 0, fontSize: "var(--text-xs)", color: "var(--text-muted)", marginTop: 2 }}>
                Model Confidence based on {forecast.history_days_used} days of historical signals
              </p>
            </div>
            <span className={`badge ${meta.badge}`} style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <BrainCircuit size={14} /> {meta.label}
            </span>
          </div>

          {forecast.reason && (
            <div style={{ background: "var(--warning-bg)", color: "var(--warning-text)", padding: "var(--space-3)", borderRadius: "var(--radius-md)", marginBottom: "var(--space-6)", fontSize: "var(--text-sm)", border: "1px solid var(--warning-border)", display: "flex", alignItems: "flex-start", gap: 8 }}>
              <HelpCircle size={18} style={{ flexShrink: 0, marginTop: 2 }} />
              <span>{forecast.reason}</span>
            </div>
          )}

          <div style={{ height: 320, background: "var(--bg-app)", borderRadius: "var(--radius-lg)", padding: "var(--space-4)", border: "1px solid var(--border-subtle)" }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={forecast.forecast}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border-subtle)" />
                <XAxis dataKey="date" fontSize={11} stroke="var(--text-muted)" tickFormatter={(d) => d.slice(5)} tickLine={false} axisLine={false} />
                <YAxis fontSize={11} stroke="var(--text-muted)" tickLine={false} axisLine={false} />
                <Tooltip 
                  contentStyle={{ background: "var(--bg-surface)", border: "none", borderRadius: "var(--radius-md)", boxShadow: "var(--shadow-lg)", fontSize: "var(--text-sm)" }}
                  itemStyle={{ color: "var(--primary-600)", fontWeight: 600 }}
                />
                <Line type="monotone" dataKey="predicted_qty" stroke="var(--primary-500)" strokeWidth={3} dot={{ fill: "var(--primary-600)", r: 4, strokeWidth: 0 }} activeDot={{ r: 6 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </motion.div>
      )}
    </motion.div>
  );
}

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
    return (
      <motion.div 
        initial={{ opacity: 0, height: 0 }} 
        animate={{ opacity: 1, height: "auto" }}
        style={{ marginTop: "var(--space-3)", background: "var(--info-bg)", border: "1px solid var(--info-border)", borderRadius: "var(--radius-md)", padding: "var(--space-3)", fontSize: "var(--text-sm)", color: "var(--info-text)", lineHeight: 1.6, position: "relative", overflow: "hidden" }}
      >
        <div style={{ position: "absolute", right: -20, top: -20, opacity: 0.1 }}>
          <Sparkles size={100} />
        </div>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 8, position: "relative", zIndex: 1 }}>
          <Sparkles size={18} style={{ flexShrink: 0, marginTop: 2 }} />
          <span>{explanation}</span>
        </div>
      </motion.div>
    );
  }
  return (
    <button className="btn btn-ghost" style={{ marginTop: "var(--space-2)", fontSize: "var(--text-xs)", padding: "4px 10px", display: "inline-flex" }} onClick={handleExplain} disabled={loading}>
      {loading ? <Activity size={14} style={{ animation: "spin 2s linear infinite" }} /> : <><Sparkles size={14} /> Explain with AI</>}
    </button>
  );
}

function AnomalyTab() {
  const [priceJumps, setPriceJumps] = useState(null);
  const [stockAdj, setStockAdj] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.getPriceJumpAnomalies(180), api.getStockAdjustmentAnomalies(90)])
      .then(([p, s]) => { setPriceJumps(p); setStockAdj(s); })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "var(--space-10)" }}>
      <Activity size={32} color="var(--primary-500)" style={{ animation: "spin 2s linear infinite", marginBottom: "var(--space-4)" }} />
      <p style={{ color: "var(--text-muted)" }}>Scanning operational ledger for statistical deviations...</p>
    </div>
  );

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }} style={{ display: "grid", gridTemplateColumns: "1fr", gap: "var(--space-6)" }}>
      <div className="card">
        <div className="flex-between" style={{ marginBottom: "var(--space-2)" }}>
          <h3 style={{ margin: 0, display: "flex", alignItems: "center", gap: 8, fontSize: "var(--text-lg)" }}>
            <Activity size={20} color="var(--accent-500)" /> Rate Fluctuations
          </h3>
          <span className={`badge ${(METHOD_META[priceJumps.method] || {}).badge || "manual"}`} style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <BrainCircuit size={12} /> {(METHOD_META[priceJumps.method] || {}).label || priceJumps.method}
          </span>
        </div>
        
        {!priceJumps.has_sufficient_data && (
          <p style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)", marginBottom: "var(--space-4)" }}>
            Operating on reduced sample size ({priceJumps.sample_size} records). Statistical fallback active until IsolationForest dataset requirements are met.
          </p>
        )}
        
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
          {priceJumps.anomalies.length === 0 ? (
            <div className="empty-state" style={{ padding: "var(--space-6)" }}>
              <ShieldAlert size={24} className="empty-state-icon" style={{ opacity: 0.5 }} />
              <p style={{ margin: 0, fontSize: "var(--text-sm)" }}>No rate anomalies detected in window.</p>
            </div>
          ) : (
            priceJumps.anomalies.map((a) => (
              <div key={a.rate_history_id} style={{ background: "var(--bg-app)", padding: "var(--space-4)", borderRadius: "var(--radius-md)", border: "1px solid var(--border-subtle)" }}>
                <div className="flex-between" style={{ alignItems: "flex-start" }}>
                  <div>
                    <strong style={{ fontSize: "var(--text-base)", display: "block", marginBottom: 2 }}>{a.medicine_name}</strong>
                    <div style={{ fontSize: "var(--text-sm)", color: "var(--text-muted)", display: "flex", alignItems: "center", gap: 6 }}>
                      {formatMoney(a.old_rate)} <ArrowRight size={12} /> {formatMoney(a.new_rate)} <span style={{ opacity: 0.5 }}>•</span> {new Date(a.changed_at).toLocaleDateString()}
                    </div>
                  </div>
                  <span className={`badge ${a.pct_change >= 0 ? "unmatched" : "learned"}`} style={{ display: "flex", alignItems: "center", gap: 4, fontSize: "var(--text-sm)", padding: "4px 8px" }}>
                    {a.pct_change >= 0 ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />} {Math.abs(a.pct_change)}%
                  </span>
                </div>
                <ExplainButton anomaly={a} />
              </div>
            ))
          )}
        </div>
      </div>

      <div className="card">
        <div className="flex-between" style={{ marginBottom: "var(--space-2)" }}>
          <h3 style={{ margin: 0, display: "flex", alignItems: "center", gap: 8, fontSize: "var(--text-lg)" }}>
            <Package size={20} color="var(--accent-500)" /> Inventory Drift
          </h3>
          <span className={`badge ${(METHOD_META[stockAdj.method] || {}).badge || "manual"}`} style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <BrainCircuit size={12} /> {(METHOD_META[stockAdj.method] || {}).label || stockAdj.method}
          </span>
        </div>
        
        {stockAdj.unattributed_count > 0 && (
          <p style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)", marginBottom: "var(--space-4)" }}>
            Excluded {stockAdj.unattributed_count} legacy adjustments (missing staff attribution) from cohort analysis.
          </p>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
          {stockAdj.flagged_adjustments.length === 0 ? (
            <div className="empty-state" style={{ padding: "var(--space-6)" }}>
              <ShieldAlert size={24} className="empty-state-icon" style={{ opacity: 0.5 }} />
              <p style={{ margin: 0, fontSize: "var(--text-sm)" }}>No critical inventory drift detected.</p>
            </div>
          ) : (
            stockAdj.flagged_adjustments.map((a) => (
              <div key={a.stock_ledger_id} style={{ background: "var(--bg-app)", padding: "var(--space-4)", borderRadius: "var(--radius-md)", border: "1px solid var(--border-subtle)" }}>
                <div className="flex-between" style={{ alignItems: "flex-start" }}>
                  <div>
                    <strong style={{ fontSize: "var(--text-base)", display: "block", marginBottom: 2 }}>{a.medicine_name}</strong>
                    <div style={{ fontSize: "var(--text-sm)", color: "var(--text-muted)", display: "flex", alignItems: "center", gap: 6 }}>
                      <span style={{ color: a.change_qty > 0 ? "var(--success-text)" : "var(--danger-text)", fontWeight: 600 }}>
                        {a.change_qty > 0 ? "+" : ""}{a.change_qty} units
                      </span> 
                      <span style={{ opacity: 0.5 }}>•</span> {a.created_by_username || "Unattributed"} <span style={{ opacity: 0.5 }}>•</span> {new Date(a.created_at).toLocaleDateString()}
                    </div>
                    {a.note && <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)", marginTop: 6, fontStyle: "italic", borderLeft: "2px solid var(--border-strong)", paddingLeft: 8 }}>"{a.note}"</div>}
                  </div>
                </div>
                <ExplainButton anomaly={a} />
              </div>
            ))
          )}
        </div>

        {stockAdj.staff_summary.length > 0 && (
          <div style={{ marginTop: "var(--space-8)" }}>
            <h4 style={{ marginBottom: "var(--space-4)", fontSize: "var(--text-sm)", textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-muted)" }}>Cohort Analysis: Staff Drift Representation</h4>
            <div className="table-container">
              <table className="table">
                <tbody>
                  {stockAdj.staff_summary.map((s) => (
                    <tr key={s.user_id}>
                      <td style={{ fontWeight: 500 }}>{s.username}</td>
                      <td style={{ color: "var(--text-muted)" }}>{s.adjustment_count} event(s)</td>
                      <td>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <div style={{ flex: 1, height: 6, background: "var(--border-subtle)", borderRadius: 3, overflow: "hidden" }}>
                            <div style={{ width: `${s.share_pct}%`, height: "100%", background: s.is_over_represented ? "var(--danger-text)" : "var(--primary-500)", borderRadius: 3 }} />
                          </div>
                          <span style={{ fontSize: "var(--text-xs)", width: 32, textAlign: "right", color: s.is_over_represented ? "var(--danger-text)" : "var(--text-main)" }}>{s.share_pct}%</span>
                        </div>
                      </td>
                      <td style={{ textAlign: "right" }}>
                        {s.is_over_represented && <span className="badge unmatched">Statistical Outlier</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </motion.div>
  );
}

export default function Predictive() {
  const [tab, setTab] = useState("forecast");

  return (
    <div style={{ paddingBottom: "var(--space-10)" }}>
      <div className="card" style={{ marginBottom: "var(--space-6)" }}>
        <h1 style={{ display: "flex", alignItems: "center", gap: 12, fontSize: "var(--text-3xl)", marginBottom: "var(--space-2)" }}>
          <Lightbulb size={32} color="var(--primary-500)" /> Predictive Intelligence
        </h1>
        <p style={{ color: "var(--text-muted)", fontSize: "var(--text-base)", marginBottom: "var(--space-6)" }}>
          Machine learning forecasts and statistical anomaly detection. Engineered to flag deviations without disrupting workflows.
        </p>
        
        <div className="tabs" style={{ marginBottom: 0, borderBottom: "1px solid var(--border-subtle)" }}>
          <button 
            className={`tab-btn ${tab === "forecast" ? "active" : ""}`} 
            onClick={() => setTab("forecast")}
            style={{ display: "flex", alignItems: "center", gap: 6, padding: "var(--space-3) var(--space-4)" }}
          >
            <TrendingUp size={16} /> Demand Forecast
          </button>
          <button 
            className={`tab-btn ${tab === "anomalies" ? "active" : ""}`} 
            onClick={() => setTab("anomalies")}
            style={{ display: "flex", alignItems: "center", gap: 6, padding: "var(--space-3) var(--space-4)" }}
          >
            <Activity size={16} /> Deviation Reports
          </button>
        </div>
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={tab}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          transition={{ duration: 0.2 }}
        >
          {tab === "forecast" && <ForecastTab />}
          {tab === "anomalies" && <AnomalyTab />}
        </motion.div>
      </AnimatePresence>

      <style>{`
        @keyframes spin { 100% { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}