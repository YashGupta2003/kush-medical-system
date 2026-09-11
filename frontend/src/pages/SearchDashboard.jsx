import React, { useEffect, useState, useMemo } from "react";
import { Link } from "react-router-dom";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { api } from "../api/client.js";
import { Search, Save, RefreshCw, Activity, ArrowRight, TrendingUp, TrendingDown, Box, PackageOpen, X, Sparkles } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import StockSparkline from "../components/StockSparkline.jsx";
import { useAuth } from "../auth/AuthContext.jsx";

const PAGE_SIZE = 50;

export default function MedicineSearch() {
  const { user } = useAuth();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(null);
  const [history, setHistory] = useState([]);
  const [compositionInput, setCompositionInput] = useState("");
  const [savingComposition, setSavingComposition] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .browseMedicines({ q: query, page, page_size: PAGE_SIZE })
      .then((data) => {
        if (cancelled) return;
        setResults((prev) => (page === 1 ? data.items : [...prev, ...data.items]));
        setTotal(data.total);
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [query, page]);

  function handleSearchChange(e) {
    setQuery(e.target.value);
    setPage(1); 
  }

  async function selectMedicine(med) {
    setSelected(med);
    setCompositionInput(med.composition || "");
    try {
      const h = await api.getMedicineHistory(med.id);
      setHistory(
        h
          .slice()
          .reverse()
          .map((r) => ({
            date: new Date(r.changed_at).toLocaleDateString(),
            net_rate: r.new_net_rate,
          }))
      );
    } catch {
      setHistory([]);
    }
  }

  async function handleSaveComposition() {
    if (!selected || !compositionInput.trim()) return;
    setSavingComposition(true);
    try {
      const updated = await api.updateComposition(selected.id, compositionInput.trim());
      setSelected(updated);
      setResults((prev) => prev.map((m) => (m.id === updated.id ? { ...m, composition: updated.composition } : m)));
    } finally {
      setSavingComposition(false);
    }
  }

  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good Morning" : hour < 18 ? "Good Afternoon" : "Good Evening";

  const motivationalQuotes = [
    "Every prescription filled is a life improved. Let's make today count.",
    "Your dedication keeps the community healthy. We're here to keep your business healthy.",
    "Great things in business are never done by one person. Let AI handle the heavy lifting.",
    "Efficiency is doing things right. Let's optimize your pharmacy today.",
    "Innovation distinguishes between a leader and a follower. Welcome to the future.",
    "Small daily improvements are the key to staggering long-term results.",
    "Success is the sum of small efforts, repeated day in and day out.",
    "A healthy business starts with a healthy inventory. Let's review the stock."
  ];

  // Pick a random quote only once per mount
  const quote = React.useMemo(() => motivationalQuotes[Math.floor(Math.random() * motivationalQuotes.length)], []);

  return (
    <div style={{ paddingBottom: "var(--space-10)" }}>
      {/* ── Magnificent Dynamic Welcome Banner ── */}
      <motion.div 
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ type: "spring", stiffness: 300, damping: 25 }}
        style={{
          position: "relative",
          background: "linear-gradient(135deg, var(--bg-surface), var(--primary-50))",
          borderRadius: "var(--radius-xl)",
          padding: "var(--space-8)",
          marginBottom: "var(--space-8)",
          border: "1px solid var(--border-subtle)",
          boxShadow: "0 10px 40px rgba(16, 185, 129, 0.05)",
          overflow: "hidden"
        }}
      >
        <div style={{ position: "absolute", right: "-10%", top: "-50%", width: "40%", height: "200%", background: "radial-gradient(circle, var(--primary-100) 0%, transparent 70%)", filter: "blur(60px)", opacity: 0.6, pointerEvents: "none" }} />
        <div style={{ display: "flex", alignItems: "center", gap: 20, position: "relative", zIndex: 1 }}>
          <motion.div
            initial={{ scale: 0, rotate: -20 }}
            animate={{ scale: 1, rotate: 0 }}
            transition={{ delay: 0.2, type: "spring", stiffness: 200 }}
            style={{ width: 64, height: 64, borderRadius: 16, background: "linear-gradient(135deg, var(--primary-500), var(--primary-700))", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "0 8px 24px rgba(16, 185, 129, 0.3)", flexShrink: 0 }}
          >
            <Sparkles size={32} />
          </motion.div>
          <div>
            <motion.p initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.3 }} style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.1em", margin: "0 0 4px" }}>
              {greeting}, {user?.full_name?.split(" ")[0] || "Pharmacist"}
            </motion.p>
            <motion.h1 initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4, type: "spring", stiffness: 300 }} style={{ fontSize: "clamp(2rem, 4vw, 3rem)", fontWeight: 800, margin: "0 0 8px", letterSpacing: "-0.03em", color: "var(--text-main)", lineHeight: 1.1 }}>
              Welcome to <span style={{ background: "linear-gradient(to right, var(--primary-600), var(--primary-800))", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>{user?.shop_name || "PharmOS"}</span>
            </motion.h1>
            <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.6 }} style={{ margin: 0, color: "var(--text-muted)", fontSize: "1.05rem", fontStyle: "italic", borderLeft: "3px solid var(--primary-400)", paddingLeft: 12 }}>
              "{quote}"
            </motion.p>
          </div>
        </div>
      </motion.div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "var(--space-6)" }}>
        
        {/* Left Panel: Search & Directory */}
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
          
          <div className="card" style={{ padding: "var(--space-6)" }}>
            <div style={{ position: "relative" }}>
              <div style={{ position: "absolute", left: 16, top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }}>
                <Search size={20} />
              </div>
              <input
                className="input"
                style={{ 
                  width: "100%", paddingLeft: 48, paddingRight: 16, 
                  paddingTop: 16, paddingBottom: 16, fontSize: "var(--text-lg)",
                  borderRadius: "var(--radius-xl)", background: "var(--bg-app)"
                }}
                placeholder="Search master directory by name, company, or salt..."
                value={query}
                onChange={handleSearchChange}
              />
            </div>
            
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "var(--space-4)" }}>
              <span style={{ color: "var(--text-muted)", fontSize: "var(--text-sm)", fontWeight: 500 }}>
                {total > 0 ? `Displaying ${results.length} of ${total} records` : "Scanning directory..."}
              </span>
              {loading && <Activity size={16} className="text-muted" style={{ animation: "spin 2s linear infinite" }} />}
            </div>
          </div>

          <div className="card table-container" style={{ padding: 0, overflow: "hidden" }}>
             <div style={{ overflowX: "auto" }}>
              <table className="table">
                <thead>
                  <tr>
                    <th>Particulars</th>
                    <th>Unit</th>
                    <th>MRP</th>
                    <th>Net Rate</th>
                    <th>Stock</th>
                    <th>Company</th>
                    <th>Composition</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((m) => {
                    const isLow = m.low_stock_threshold != null && m.current_stock != null && m.current_stock < m.low_stock_threshold;
                    const isSelected = selected?.id === m.id;
                    return (
                      <tr 
                        key={m.id} 
                        onClick={() => selectMedicine(m)} 
                        style={{ cursor: "pointer", background: isSelected ? "var(--bg-surface-hover)" : undefined }}
                      >
                        <td style={{ fontWeight: 500, color: "var(--primary-600)" }}>{m.particulars}</td>
                        <td>{m.unit}</td>
                        <td>₹{m.mrp}</td>
                        <td>₹{m.net_rate}</td>
                        <td>
                          <div style={{ display: "flex", alignItems: "center" }}>
                            {isLow ? (
                              <span className="badge unmatched" style={{ display: "flex", alignItems: "center", gap: 4, width: "fit-content" }}>
                                <TrendingDown size={12} /> {m.current_stock} Low
                              </span>
                            ) : (
                              <span style={{ color: m.current_stock ? "var(--text-main)" : "var(--text-muted)" }}>
                                {m.current_stock ?? "—"}
                              </span>
                            )}
                            <StockSparkline baseValue={m.current_stock} seed={m.id} color={isLow ? "var(--danger-500)" : "var(--primary-500)"} />
                          </div>
                        </td>
                        <td style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)" }}>{m.company || "—"}</td>
                        <td>
                          {m.composition ? (
                            <span className="badge learned">{m.composition}</span>
                          ) : (
                            <span style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)", fontStyle: "italic" }}>Not set</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {results.length < total && (
              <div style={{ padding: "var(--space-4)", textAlign: "center", borderTop: "1px solid var(--border-subtle)" }}>
                <button
                  className="btn btn-secondary"
                  disabled={loading}
                  onClick={() => setPage((p) => p + 1)}
                >
                  {loading ? "Scanning..." : `Load More (${total - results.length} remaining)`}
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Right Panel: Contextual Intel Drawer */}
        <AnimatePresence>
          {selected && (
            <>
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
                onClick={() => setSelected(null)}
                style={{
                  position: "fixed", top: 0, left: 0, width: "100vw", height: "100vh",
                  background: "rgba(0,0,0,0.4)", backdropFilter: "blur(2px)",
                  zIndex: 99998
                }}
              />
              <motion.div 
                initial={{ opacity: 0, x: "100%" }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: "100%" }}
                transition={{ type: "spring", stiffness: 300, damping: 30 }}
                className="card card-raised" 
                style={{ 
                  position: "fixed", top: 0, right: 0, width: "100%", maxWidth: "450px", height: "100vh",
                  zIndex: 99999, borderRadius: 0, overflowY: "auto", borderLeft: "1px solid var(--border-subtle)",
                  padding: "var(--space-6)", margin: 0, background: "var(--bg-surface)"
                }}
              >
                <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: "var(--space-4)" }}>
                  <div>
                    <h3 style={{ fontSize: "var(--text-xl)", marginBottom: "var(--space-1)" }}>{selected.particulars}</h3>
                    <p style={{ color: "var(--text-muted)", fontSize: "var(--text-sm)", margin: 0 }}>
                      {selected.company || "Unknown Company"} • {selected.unit}
                    </p>
                  </div>
                  <button onClick={() => setSelected(null)} style={{ background: "var(--bg-app)", border: "1px solid var(--border-subtle)", cursor: "pointer", color: "var(--text-muted)", width: 36, height: 36, display: "flex", alignItems: "center", justifyContent: "center", borderRadius: "var(--radius-full)" }}>
                    <X size={18} />
                  </button>
                </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-3)", marginBottom: "var(--space-6)" }}>
                <div className="stat-card" style={{ padding: "var(--space-3)" }}>
                  <span className="stat-label">MRP</span>
                  <span className="stat-value" style={{ fontSize: "var(--text-2xl)" }}>₹{selected.mrp}</span>
                </div>
                <div className="stat-card" style={{ padding: "var(--space-3)" }}>
                  <span className="stat-label">Net Rate</span>
                  <span className="stat-value" style={{ fontSize: "var(--text-2xl)", color: "var(--primary-600)" }}>₹{selected.net_rate}</span>
                </div>
              </div>

              <div style={{ marginBottom: "var(--space-6)" }}>
                <label style={{ display: "block", fontSize: "var(--text-xs)", fontWeight: 600, color: "var(--text-muted)", marginBottom: "var(--space-2)", textTransform: "uppercase" }}>
                  Chemical Composition
                </label>
                <div style={{ display: "flex", gap: "var(--space-2)" }}>
                  <input
                    className="input"
                    placeholder="e.g. Paracetamol 650mg"
                    value={compositionInput}
                    onChange={(e) => setCompositionInput(e.target.value)}
                  />
                  <button className="btn btn-primary" onClick={handleSaveComposition} disabled={savingComposition} title="Save Composition">
                    {savingComposition ? <Activity size={16} style={{ animation: "spin 2s linear infinite" }} /> : <Save size={16} />}
                  </button>
                </div>
              </div>

              <div style={{ marginBottom: "var(--space-6)" }}>
                <label style={{ display: "block", fontSize: "var(--text-xs)", fontWeight: 600, color: "var(--text-muted)", marginBottom: "var(--space-2)", textTransform: "uppercase" }}>
                  Procurement History
                </label>
                <div style={{ height: 180, background: "var(--bg-app)", borderRadius: "var(--radius-md)", padding: "var(--space-3)", border: "1px solid var(--border-subtle)" }}>
                  {history.length > 1 ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={history}>
                        <XAxis dataKey="date" fontSize={10} stroke="var(--text-muted)" tickLine={false} axisLine={false} />
                        <YAxis fontSize={10} stroke="var(--text-muted)" tickLine={false} axisLine={false} width={30} />
                        <Tooltip 
                          contentStyle={{ background: "var(--bg-surface)", border: "none", borderRadius: "var(--radius-md)", boxShadow: "var(--shadow-lg)", fontSize: "var(--text-xs)" }} 
                          itemStyle={{ color: "var(--primary-600)", fontWeight: 600 }}
                        />
                        <Line type="monotone" dataKey="net_rate" stroke="var(--primary-500)" strokeWidth={3} dot={{ fill: "var(--primary-600)", strokeWidth: 0, r: 4 }} activeDot={{ r: 6 }} />
                      </LineChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="empty-state" style={{ padding: "var(--space-4)" }}>
                      <PackageOpen size={24} className="empty-state-icon" style={{ marginBottom: "var(--space-2)" }} />
                      <p style={{ fontSize: "var(--text-xs)", margin: 0 }}>Insufficient procurement data.</p>
                    </div>
                  )}
                </div>
              </div>

              <Link to={`/substitutes?medicine_id=${selected.id}`} style={{ textDecoration: "none" }}>
                <button className="btn btn-secondary" style={{ width: "100%", justifyContent: "space-between" }}>
                  <span style={{ display: "flex", alignItems: "center", gap: 8 }}><RefreshCw size={16} /> Find Substitutes</span>
                  <ArrowRight size={16} />
                </button>
              </Link>
              </motion.div>
            </>
          )}
        </AnimatePresence>
      </div>

      <style>{`
        @keyframes spin { 100% { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}