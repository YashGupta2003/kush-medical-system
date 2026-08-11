import { useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  TrendingDown, TrendingUp, AlertTriangle, BarChart2, Search,
  ArrowUpRight, ArrowDownRight, DollarSign, Award, ShieldAlert,
  ChevronDown, Loader2, Info, RefreshCw, Star, BadgeCheck
} from "lucide-react";
import { api } from "../api/client.js";

/* ─── Helpers ─────────────────────────────────────────────────────────── */
function fmtMoney(n) {
  if (n == null) return "—";
  return "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}
function fmtPct(n, showSign = false) {
  if (n == null) return "—";
  const s = (showSign && n > 0 ? "+" : "") + Number(n).toFixed(1) + "%";
  return s;
}

const STATUS_META = {
  healthy:  { label: "Healthy",  bg: "var(--success-bg)",  text: "var(--success-text)",  border: "var(--success-border)"  },
  thin:     { label: "Thin",     bg: "var(--warning-bg)",  text: "var(--warning-text)",  border: "var(--warning-border)"  },
  critical: { label: "Critical", bg: "var(--danger-bg)",   text: "var(--danger-text)",   border: "var(--danger-border)"   },
  unpriced: { label: "Unpriced", bg: "var(--neutral-100)", text: "var(--neutral-500)",   border: "var(--neutral-200)"     },
};

const SEVERITY_META = {
  mild:     { bg: "var(--info-bg)",    text: "var(--info-text)",    border: "var(--info-border)"    },
  moderate: { bg: "var(--warning-bg)", text: "var(--warning-text)", border: "var(--warning-border)" },
  severe:   { bg: "var(--danger-bg)",  text: "var(--danger-text)",  border: "var(--danger-border)"  },
};

/* ─── Status Badge ─────────────────────────────────────────────────────── */
function StatusBadge({ status }) {
  const m = STATUS_META[status] || STATUS_META.unpriced;
  return (
    <span style={{ padding: "2px 8px", borderRadius: 99, fontSize: "var(--text-xs)", fontWeight: 700, background: m.bg, color: m.text, border: `1px solid ${m.border}`, textTransform: "uppercase", letterSpacing: "0.05em" }}>
      {m.label}
    </span>
  );
}
function SeverityBadge({ severity }) {
  const m = SEVERITY_META[severity] || SEVERITY_META.mild;
  return (
    <span style={{ padding: "2px 8px", borderRadius: 99, fontSize: "var(--text-xs)", fontWeight: 700, background: m.bg, color: m.text, border: `1px solid ${m.border}` }}>
      {severity}
    </span>
  );
}

/* ─── Tab Button ───────────────────────────────────────────────────────── */
function TabBtn({ active, onClick, icon, label, badge }) {
  return (
    <motion.button
      onClick={onClick}
      whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}
      style={{
        display: "flex", alignItems: "center", gap: 7, padding: "9px 18px",
        borderRadius: "var(--radius-full)", border: "1px solid",
        borderColor: active ? "var(--primary-500)" : "var(--border-subtle)",
        background: active ? "var(--primary-500)" : "var(--bg-surface)",
        color: active ? "#fff" : "var(--text-main)",
        fontWeight: 600, fontSize: "var(--text-sm)", cursor: "pointer",
        transition: "all 0.2s"
      }}
    >
      {icon} {label}
      {badge != null && badge > 0 && (
        <span style={{ background: active ? "rgba(255,255,255,0.25)" : "var(--danger-text)", color: active ? "#fff" : "#fff", borderRadius: 99, padding: "0px 6px", fontSize: "var(--text-xs)", fontWeight: 700 }}>
          {badge}
        </span>
      )}
    </motion.button>
  );
}

/* ─── Margin List Tab ──────────────────────────────────────────────────── */
function MarginListTab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");

  useEffect(() => {
    setLoading(true);
    api.getProfitMargins()
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const filtered = (data || [])
    .filter(m => filter === "all" || m.status === filter)
    .filter(m => !search || (m.name || "").toLowerCase().includes(search.toLowerCase()));

  const counts = { healthy: 0, thin: 0, critical: 0, unpriced: 0 };
  (data || []).forEach(m => { if (counts[m.status] !== undefined) counts[m.status]++; });

  if (loading) return <div style={{ textAlign: "center", padding: 40 }}><Loader2 size={24} className="spin" color="var(--primary-500)" /></div>;
  if (error) return <p style={{ color: "var(--danger-text)", padding: 20 }}>{error}</p>;

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      {/* Summary chips */}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: "var(--space-4)" }}>
        {Object.entries(counts).map(([key, cnt]) => {
          const m = STATUS_META[key];
          return (
            <button key={key} onClick={() => setFilter(f => f === key ? "all" : key)}
              style={{ padding: "5px 14px", borderRadius: 99, fontSize: "var(--text-xs)", fontWeight: 700, cursor: "pointer", border: `1px solid ${filter === key ? m.border : "var(--border-subtle)"}`, background: filter === key ? m.bg : "var(--bg-surface)", color: filter === key ? m.text : "var(--text-muted)", transition: "all 0.15s" }}>
              {m.label}: {cnt}
            </button>
          );
        })}
        <div style={{ position: "relative", flex: 1, minWidth: 180 }}>
          <Search size={13} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }} />
          <input className="input" style={{ width: "100%", paddingLeft: 30, height: 34, fontSize: "var(--text-sm)" }}
            placeholder="Filter by name…" value={search} onChange={e => setSearch(e.target.value)} />
        </div>
      </div>

      <div className="table-container" style={{ borderRadius: "var(--radius-md)" }}>
        <table className="table">
          <thead>
            <tr>
              <th>Medicine</th>
              <th style={{ textAlign: "right" }}>MRP</th>
              <th style={{ textAlign: "right" }}>Buy Rate</th>
              <th style={{ textAlign: "right" }}>Margin</th>
              <th style={{ textAlign: "center" }}>Health</th>
            </tr>
          </thead>
          <tbody>
            {filtered.slice(0, 200).map((m, i) => (
              <motion.tr key={m.medicine_id} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i, 20) * 0.02 }}>
                <td style={{ fontWeight: 500, maxWidth: 300 }}>{m.name}</td>
                <td style={{ textAlign: "right", color: "var(--text-muted)", fontSize: "var(--text-sm)" }}>{fmtMoney(m.mrp)}</td>
                <td style={{ textAlign: "right", color: "var(--text-muted)", fontSize: "var(--text-sm)" }}>{fmtMoney(m.net_rate)}</td>
                <td style={{ textAlign: "right" }}>
                  <span style={{ fontWeight: 700, fontSize: "var(--text-base)", color: m.margin_pct > 20 ? "var(--success-text)" : m.margin_pct > 10 ? "var(--warning-text)" : "var(--danger-text)" }}>
                    {m.margin_pct != null ? fmtPct(m.margin_pct) : "—"}
                  </span>
                </td>
                <td style={{ textAlign: "center" }}><StatusBadge status={m.status} /></td>
              </motion.tr>
            ))}
            {filtered.length === 0 && (
              <tr><td colSpan={5} style={{ textAlign: "center", color: "var(--text-muted)", padding: 32 }}>No medicines match this filter.</td></tr>
            )}
          </tbody>
        </table>
      </div>
      {filtered.length > 200 && (
        <p style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)", textAlign: "center", marginTop: 8 }}>Showing first 200 of {filtered.length}. Use search to narrow results.</p>
      )}
    </motion.div>
  );
}

/* ─── Compression Tab ──────────────────────────────────────────────────── */
function CompressionTab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [severity, setSeverity] = useState("all");
  const [days, setDays] = useState(90);

  const load = useCallback(() => {
    setLoading(true); setError("");
    api.getProfitCompression({ severity: severity === "all" ? null : severity, days })
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [severity, days]);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div style={{ textAlign: "center", padding: 40 }}><Loader2 size={24} className="spin" color="var(--primary-500)" /></div>;
  if (error) return <p style={{ color: "var(--danger-text)", padding: 20 }}>{error}</p>;

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: "var(--space-4)", flexWrap: "wrap" }}>
        <div style={{ display: "flex", gap: 8 }}>
          {["all", "mild", "moderate", "severe"].map(s => (
            <button key={s} onClick={() => setSeverity(s)}
              style={{ padding: "5px 14px", borderRadius: 99, fontSize: "var(--text-xs)", fontWeight: 700, cursor: "pointer", border: "1px solid", borderColor: severity === s ? "var(--primary-500)" : "var(--border-subtle)", background: severity === s ? "var(--primary-50)" : "var(--bg-surface)", color: severity === s ? "var(--primary-600)" : "var(--text-muted)", transition: "all 0.15s" }}>
              {s === "all" ? "All" : s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>
        <select className="input" style={{ height: 34, width: "auto", fontSize: "var(--text-sm)" }} value={days} onChange={e => setDays(Number(e.target.value))}>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
          <option value={180}>Last 180 days</option>
        </select>
      </div>

      {(!data || data.length === 0) ? (
        <div className="card" style={{ textAlign: "center", padding: "var(--space-10)" }}>
          <BadgeCheck size={40} color="var(--success-text)" style={{ margin: "0 auto 12px" }} />
          <h4>No margin compression detected</h4>
          <p style={{ color: "var(--text-muted)", fontSize: "var(--text-sm)" }}>All distributors are pricing fairly within the selected window.</p>
        </div>
      ) : (
        <>
          <div style={{ background: "var(--warning-bg)", border: "1px solid var(--warning-border)", borderRadius: "var(--radius-md)", padding: "10px 16px", marginBottom: "var(--space-4)", display: "flex", gap: 8, alignItems: "flex-start" }}>
            <ShieldAlert size={15} color="var(--warning-text)" style={{ marginTop: 1 }} />
            <p style={{ fontSize: "var(--text-xs)", color: "var(--warning-text)", margin: 0, lineHeight: 1.6 }}>
              <strong>{data.length} medicine(s) detected</strong> where your purchase rate increased but MRP remained the same — your profit margin is being silently squeezed.
            </p>
          </div>
          <div className="table-container" style={{ borderRadius: "var(--radius-md)" }}>
            <table className="table">
              <thead>
                <tr>
                  <th>Medicine</th>
                  <th style={{ textAlign: "center" }}>Type</th>
                  <th style={{ textAlign: "right" }}>Old Margin</th>
                  <th style={{ textAlign: "right" }}>New Margin</th>
                  <th style={{ textAlign: "right" }}>Margin Δ</th>
                  <th style={{ textAlign: "center" }}>Severity</th>
                </tr>
              </thead>
              <tbody>
                {data.map((c, i) => (
                  <motion.tr key={c.medicine_id} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.03 }}>
                    <td style={{ fontWeight: 600 }}>{c.medicine_name}</td>
                    <td style={{ textAlign: "center" }}>
                      <span style={{ fontSize: "var(--text-xs)", background: "var(--neutral-100)", color: "var(--neutral-700)", padding: "2px 8px", borderRadius: 6, fontWeight: 600 }}>
                        {c.compression_type === "buy_rate_up" ? "Rate ↑" : c.compression_type === "mrp_drop" ? "MRP ↓" : "Both"}
                      </span>
                    </td>
                    <td style={{ textAlign: "right", color: "var(--text-muted)", fontSize: "var(--text-sm)" }}>{fmtPct(c.previous_margin_pct)}</td>
                    <td style={{ textAlign: "right", fontWeight: 700, color: c.current_margin_pct < c.previous_margin_pct ? "var(--danger-text)" : "var(--success-text)" }}>
                      {fmtPct(c.current_margin_pct)}
                    </td>
                    <td style={{ textAlign: "right" }}>
                      <span style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 3, color: "var(--danger-text)", fontWeight: 700 }}>
                        <TrendingDown size={13} /> {fmtPct(c.margin_delta_pct, true)}
                      </span>
                    </td>
                    <td style={{ textAlign: "center" }}><SeverityBadge severity={c.compression_severity} /></td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </motion.div>
  );
}

/* ─── Best-Margin Substitutes Tab ─────────────────────────────────────── */
function SubstitutesTab() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [medicine, setMedicine] = useState(null);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (query.trim().length < 2) { setResults([]); return; }
    const t = setTimeout(() => api.browseMedicines({ q: query, page: 1, page_size: 8 }).then(d => setResults(d.items)), 250);
    return () => clearTimeout(t);
  }, [query]);

  function selectMed(m) {
    setMedicine(m); setQuery(""); setResults([]); setLoading(true);
    api.getBestMarginSubstitutes(m.id).then(setData).catch(() => setData(null)).finally(() => setLoading(false));
  }

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      <div style={{ position: "relative", marginBottom: "var(--space-4)" }}>
        <Search size={15} style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }} />
        <input className="input" style={{ width: "100%", paddingLeft: 36 }}
          placeholder="Search a medicine to find highest-margin substitutes…"
          value={query} onChange={e => setQuery(e.target.value)} />
      </div>
      {results.length > 0 && (
        <div className="card" style={{ marginBottom: "var(--space-4)", padding: 8 }}>
          {results.map(m => (
            <motion.div key={m.id} whileHover={{ background: "var(--bg-surface-hover)" }}
              style={{ padding: "8px 12px", borderRadius: "var(--radius-md)", cursor: "pointer", display: "flex", justifyContent: "space-between" }}
              onClick={() => selectMed(m)}>
              <span style={{ fontWeight: 500, fontSize: "var(--text-sm)" }}>{m.particulars}</span>
              <span style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)" }}>{m.unit}</span>
            </motion.div>
          ))}
        </div>
      )}
      {medicine && (
        <div style={{ marginBottom: "var(--space-3)", padding: "10px 14px", background: "var(--primary-50)", borderRadius: "var(--radius-md)", display: "flex", alignItems: "center", gap: 8 }}>
          <BarChart2 size={14} color="var(--primary-600)" />
          <span style={{ fontWeight: 600, color: "var(--primary-700)", fontSize: "var(--text-sm)" }}>
            Substitutes for: {medicine.particulars}
          </span>
        </div>
      )}
      {loading && <div style={{ textAlign: "center", padding: 40 }}><Loader2 size={24} className="spin" color="var(--primary-500)" /></div>}
      {!loading && data && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <div style={{ marginBottom: "var(--space-2)", padding: "8px 12px", background: "var(--info-bg)", borderRadius: "var(--radius-md)", display: "flex", gap: 8 }}>
            <Info size={13} color="var(--info-text)" style={{ marginTop: 1 }} />
            <p style={{ fontSize: "var(--text-xs)", color: "var(--info-text)", margin: 0, lineHeight: 1.5 }}>
              Sorted by profit margin (highest first). Switching to a higher-margin substitute increases your earnings per unit sold.
            </p>
          </div>
          <div className="table-container" style={{ borderRadius: "var(--radius-md)" }}>
            <table className="table">
              <thead>
                <tr>
                  <th>Substitute Medicine</th>
                  <th>Company</th>
                  <th style={{ textAlign: "right" }}>MRP</th>
                  <th style={{ textAlign: "right" }}>Buy Rate</th>
                  <th style={{ textAlign: "right" }}>Margin</th>
                  <th style={{ textAlign: "right" }}>Stock</th>
                </tr>
              </thead>
              <tbody>
                {(data.substitutes || []).map((s, i) => (
                  <motion.tr key={s.medicine_id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.04 }}>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        {i === 0 && <Star size={13} color="var(--accent-500)" fill="var(--accent-400)" />}
                        <span style={{ fontWeight: 500 }}>{s.medicine_name || s.name}</span>
                      </div>
                    </td>
                    <td style={{ color: "var(--text-muted)", fontSize: "var(--text-sm)" }}>{s.company || "—"}</td>
                    <td style={{ textAlign: "right", fontSize: "var(--text-sm)" }}>{fmtMoney(s.mrp)}</td>
                    <td style={{ textAlign: "right", fontSize: "var(--text-sm)" }}>{fmtMoney(s.net_rate)}</td>
                    <td style={{ textAlign: "right" }}>
                      <span style={{ fontWeight: 700, color: s.margin_pct > 20 ? "var(--success-text)" : s.margin_pct > 10 ? "var(--warning-text)" : "var(--danger-text)" }}>
                        {s.margin_pct != null ? fmtPct(s.margin_pct) : "Unpriced"}
                      </span>
                    </td>
                    <td style={{ textAlign: "right" }}>
                      <span style={{ color: s.is_in_stock ? "var(--success-text)" : "var(--danger-text)", fontWeight: 600, fontSize: "var(--text-sm)" }}>
                        {s.is_in_stock ? `${s.current_stock} ✓` : "Out of stock"}
                      </span>
                    </td>
                  </motion.tr>
                ))}
                {(!data.substitutes || data.substitutes.length === 0) && (
                  <tr><td colSpan={6} style={{ textAlign: "center", color: "var(--text-muted)", padding: 32 }}>No same-salt substitutes found in catalog.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </motion.div>
      )}
      {!loading && !data && !medicine && (
        <div className="card" style={{ textAlign: "center", padding: "var(--space-10)", color: "var(--text-muted)" }}>
          <Search size={36} style={{ margin: "0 auto 12px", opacity: 0.3 }} />
          <p>Search for a medicine to see which same-salt substitutes give you the best profit margin.</p>
        </div>
      )}
    </motion.div>
  );
}

/* ─── Distributor Report Tab ───────────────────────────────────────────── */
function DistributorReportTab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api.getDistributorNegotiationReport()
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div style={{ textAlign: "center", padding: 40 }}><Loader2 size={24} className="spin" color="var(--primary-500)" /></div>;
  if (error) return <p style={{ color: "var(--danger-text)", padding: 20 }}>{error}</p>;
  if (!data || data.length === 0) return <p style={{ color: "var(--text-muted)", padding: 20 }}>No distributor data available yet. Confirm some bills first.</p>;

  const best = data[0];
  const worst = data[data.length - 1];

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      {/* Top / Bottom callout */}
      <div style={{ display: "flex", gap: "var(--space-4)", marginBottom: "var(--space-4)", flexWrap: "wrap" }}>
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="card" style={{ flex: 1, minWidth: 220, background: "var(--success-bg)", border: "1px solid var(--success-border)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <Award size={16} color="var(--success-text)" />
            <span style={{ fontSize: "var(--text-xs)", fontWeight: 700, color: "var(--success-text)", textTransform: "uppercase" }}>Best Deal</span>
          </div>
          <div style={{ fontSize: "var(--text-lg)", fontWeight: 700, color: "var(--success-text)" }}>{best.distributor_name}</div>
          <div style={{ fontSize: "var(--text-sm)", color: "var(--success-text)", opacity: 0.8 }}>Deal Score: {best.deal_score?.toFixed(1)}/100 · Avg Margin {fmtPct(best.avg_margin_across_medicines)}</div>
        </motion.div>
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }} className="card" style={{ flex: 1, minWidth: 220, background: "var(--danger-bg)", border: "1px solid var(--danger-border)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <AlertTriangle size={16} color="var(--danger-text)" />
            <span style={{ fontSize: "var(--text-xs)", fontWeight: 700, color: "var(--danger-text)", textTransform: "uppercase" }}>Needs Renegotiation</span>
          </div>
          <div style={{ fontSize: "var(--text-lg)", fontWeight: 700, color: "var(--danger-text)" }}>{worst.distributor_name}</div>
          <div style={{ fontSize: "var(--text-sm)", color: "var(--danger-text)", opacity: 0.8 }}>Deal Score: {worst.deal_score?.toFixed(1)}/100 · Avg Margin {fmtPct(worst.avg_margin_across_medicines)}</div>
        </motion.div>
      </div>

      <div className="table-container" style={{ borderRadius: "var(--radius-md)" }}>
        <table className="table">
          <thead>
            <tr>
              <th>Rank</th>
              <th>Distributor</th>
              <th style={{ textAlign: "right" }}>Avg Margin</th>
              <th>Best Medicine</th>
              <th>Worst Medicine</th>
              <th style={{ textAlign: "right" }}>Avg Price Trend</th>
              <th style={{ textAlign: "right" }}>Deal Score</th>
            </tr>
          </thead>
          <tbody>
            {data.map((d, i) => (
              <motion.tr key={d.distributor_id || i} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}>
                <td>
                  <span style={{ fontWeight: 700, color: i === 0 ? "var(--success-text)" : i === data.length - 1 ? "var(--danger-text)" : "var(--text-muted)" }}>
                    #{i + 1}
                  </span>
                </td>
                <td style={{ fontWeight: 600 }}>{d.distributor_name}</td>
                <td style={{ textAlign: "right", fontWeight: 700, color: d.avg_margin_across_medicines > 20 ? "var(--success-text)" : d.avg_margin_across_medicines > 10 ? "var(--warning-text)" : "var(--danger-text)" }}>
                  {fmtPct(d.avg_margin_across_medicines)}
                </td>
                <td style={{ fontSize: "var(--text-xs)", color: "var(--success-text)", maxWidth: 180 }}>
                  {d.best_medicine || "—"}
                </td>
                <td style={{ fontSize: "var(--text-xs)", color: "var(--danger-text)", maxWidth: 180 }}>
                  {d.worst_medicine || "—"}
                </td>
                <td style={{ textAlign: "right" }}>
                  {d.price_trend != null ? (
                    <span style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 4, color: d.price_trend > 0 ? "var(--danger-text)" : "var(--success-text)", fontWeight: 600, fontSize: "var(--text-sm)" }}>
                      {d.price_trend > 0 ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                      {fmtPct(d.price_trend, true)}/period
                    </span>
                  ) : "—"}
                </td>
                <td style={{ textAlign: "right" }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 8 }}>
                    <div style={{ width: 60, height: 6, borderRadius: 3, background: "var(--border-subtle)", overflow: "hidden" }}>
                      <div style={{ width: `${Math.min(100, Math.max(0, d.deal_score || 0))}%`, height: "100%", background: d.deal_score > 60 ? "var(--success-text)" : d.deal_score > 35 ? "var(--warning-text)" : "var(--danger-text)", borderRadius: 3, transition: "width 0.8s ease" }} />
                    </div>
                    <span style={{ fontWeight: 700, fontSize: "var(--text-sm)", color: d.deal_score > 60 ? "var(--success-text)" : d.deal_score > 35 ? "var(--warning-text)" : "var(--danger-text)" }}>
                      {d.deal_score?.toFixed(0)}
                    </span>
                  </div>
                </td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
      <p style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)", marginTop: "var(--space-3)", lineHeight: 1.6 }}>
        Deal Score = avg_margin_pct − (0.5 × avg_price_increase_pct). Higher = better deal for you. Use this report when negotiating annual contracts.
      </p>
    </motion.div>
  );
}

/* ─── Main Page ─────────────────────────────────────────────────────────── */
const TABS = [
  { id: "margins",      label: "All Margins",      icon: <BarChart2 size={14} /> },
  { id: "compression",  label: "Margin Squeeze",   icon: <TrendingDown size={14} /> },
  { id: "substitutes",  label: "Best Substitutes", icon: <ArrowUpRight size={14} /> },
  { id: "distributors", label: "Distributor Report", icon: <Award size={14} /> },
];

export default function ProfitOptimizer() {
  const [tab, setTab] = useState("margins");
  const [compressionCount, setCompressionCount] = useState(null);

  useEffect(() => {
    api.getProfitCompression({}).then(d => setCompressionCount(d?.length || 0)).catch(() => {});
  }, []);

  return (
    <div style={{ padding: "var(--space-6) var(--space-8)" }}>
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }} style={{ marginBottom: "var(--space-6)" }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 14, marginBottom: 6 }}>
          <div style={{ width: 44, height: 44, borderRadius: 12, background: "linear-gradient(135deg, #f59e0b, #d97706)", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", flexShrink: 0, boxShadow: "0 4px 12px rgba(245,158,11,0.3)" }}>
            <DollarSign size={22} />
          </div>
          <div>
            <h1 style={{ fontSize: "var(--text-2xl)", fontWeight: 800, letterSpacing: "-0.03em", marginBottom: 4, background: "linear-gradient(to right, #b45309, #f59e0b)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
              Profit Margin Optimizer
            </h1>
            <p style={{ color: "var(--text-muted)", fontSize: "var(--text-sm)", marginBottom: 0 }}>
              Detect margin compression · Find high-margin substitutes · Rank distributors by deal quality
            </p>
          </div>
        </div>
      </motion.div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: "var(--space-5)" }}>
        {TABS.map(t => (
          <TabBtn key={t.id} active={tab === t.id} onClick={() => setTab(t.id)} icon={t.icon} label={t.label}
            badge={t.id === "compression" ? compressionCount : null} />
        ))}
      </div>

      {/* Tab content */}
      <div className="card" style={{ padding: "var(--space-5)" }}>
        <AnimatePresence mode="wait">
          {tab === "margins"      && <MarginListTab key="margins" />}
          {tab === "compression"  && <CompressionTab key="compression" />}
          {tab === "substitutes"  && <SubstitutesTab key="substitutes" />}
          {tab === "distributors" && <DistributorReportTab key="distributors" />}
        </AnimatePresence>
      </div>

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        .spin { animation: spin 1s linear infinite; }
      `}</style>
    </div>
  );
}
