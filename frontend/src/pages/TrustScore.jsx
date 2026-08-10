import React, { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { api } from "../api/client.js";
import { motion, AnimatePresence } from "framer-motion";
import { Shield, ShieldAlert, ShieldCheck, ChevronDown, ChevronUp, AlertOctagon, TrendingDown, Users, BotMessageSquare, X } from "lucide-react";
import { Link } from "react-router-dom";

function formatMoney(n) {
  if (n == null) return "—";
  return "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function getScoreColor(score) {
  if (score >= 70) return "var(--success-500, #10b981)"; // green
  if (score >= 40) return "var(--warning-500, #f59e0b)"; // amber
  return "var(--danger-500, #ef4444)"; // red
}

function getConfidenceBadgeClass(conf) {
  if (conf === "high") return "badge-success";
  if (conf === "medium") return "badge-warning";
  if (conf === "low") return "badge-danger";
  return "badge-neutral";
}

// ---------------------------------------------------------------------------
// Expanded Detail View
// ---------------------------------------------------------------------------
function DistributorDetail({ id }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getTrustScore(id)
      .then(setDetail)
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div style={{ padding: 16, color: "var(--text-muted)", fontSize: 14, display: "flex", justifyContent: "center" }}>Loading details...</div>;
  if (!detail) return <div style={{ padding: 16, color: "var(--danger-500)", fontSize: 14, display: "flex", justifyContent: "center" }}>Failed to load details.</div>;

  return (
    <motion.div 
      className="trust-detail-pane"
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: "auto" }}
      exit={{ opacity: 0, height: 0 }}
      transition={{ duration: 0.2 }}
    >
      <h4 style={{ display: 'flex', alignItems: 'center', gap: 6 }}><ShieldCheck size={16} /> Contributing Factors</h4>
      <ul style={{ margin: "8px 0 20px", paddingLeft: 24, fontSize: 14, color: "var(--text-main)" }}>
        {detail.contributing_factors?.map((f, i) => <li key={i} style={{ marginBottom: 4 }}>{f}</li>) || <li>No specific factors listed.</li>}
      </ul>

      {detail.batch_collisions?.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <h4 style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--danger-600)' }}><AlertOctagon size={16} /> Batch Collisions</h4>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 8 }}>
            {detail.batch_collisions.map((c, i) => (
              <div key={i} style={{ fontSize: 13, color: "var(--text-main)", background: "var(--bg-surface)", padding: "10px 12px", borderRadius: 6, border: "1px solid var(--border-color)", display: 'flex', alignItems: 'center', gap: 8 }}>
                <Users size={14} style={{ color: 'var(--text-muted)' }} />
                <span><strong>{c.medicine_name}</strong> (Batch: {c.normalized_batch_number}) shared with {c.other_distributor_names?.join(", ")}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {detail.rate_outlier_summary && detail.rate_outlier_summary.length > 0 && (
        <div>
          <h4 style={{ display: 'flex', alignItems: 'center', gap: 6 }}><TrendingDown size={16} /> Rate Comparison (vs Market Average)</h4>
          <div style={{ background: "var(--bg-surface)", padding: 16, borderRadius: 8, border: "1px solid var(--border-color)", marginTop: 8 }}>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={detail.rate_outlier_summary} layout="vertical" margin={{ top: 5, right: 20, left: 20, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="var(--border-color)" />
                  <XAxis type="number" fontSize={12} tickFormatter={(val) => "₹" + val} stroke="var(--text-muted)" />
                  <YAxis dataKey="medicine_name" type="category" fontSize={12} width={150} stroke="var(--text-muted)" />
                  <Tooltip 
                    formatter={(val) => "₹" + val} 
                    contentStyle={{ backgroundColor: 'var(--bg-surface)', borderColor: 'var(--border-color)', color: 'var(--text-main)', borderRadius: 8 }}
                  />
                  <Bar dataKey="avg_rate" fill="var(--primary-500)" name="This Distributor" radius={[0, 4, 4, 0]} />
                  <Bar dataKey="market_avg_rate" fill="var(--success-400)" name="Market Avg" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
          </div>
        </div>
      )}
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Tab 1: Trust Scores
// ---------------------------------------------------------------------------
function TrustScoresTab() {
  const [distributors, setDistributors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState(null);

  useEffect(() => {
    api.getTrustScores()
      .then((data) => {
        // Sort ascending by default (most concerning first)
        const sorted = (data || []).sort((a, b) => (a.score || 0) - (b.score || 0));
        setDistributors(sorted);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>Loading trust scores...</div>;

  return (
    <div className="card">
      <div style={{ overflowX: "auto" }}>
        <table className="trust-table">
          <thead>
            <tr>
              <th>Distributor Name</th>
              <th>Score</th>
              <th>Confidence</th>
              <th>Factors Count</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {distributors.map((d) => (
              <React.Fragment key={d.distributor_id}>
                <tr className={expandedId === d.distributor_id ? "expanded-row-parent" : ""} onClick={() => setExpandedId(expandedId === d.distributor_id ? null : d.distributor_id)} style={{ cursor: "pointer" }}>
                  <td style={{ fontWeight: 600, color: "var(--text-main)" }}>{d.distributor_name}</td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: 2 }}>
                        <span style={{ color: getScoreColor(d.score), fontWeight: "bold", fontSize: 18 }}>
                        {d.score}
                        </span>
                        <span style={{ fontSize: 12, color: "var(--text-muted)" }}>/100</span>
                    </div>
                  </td>
                  <td>
                    <span className={`badge ${getConfidenceBadgeClass(d.confidence)}`}>{d.confidence}</span>
                  </td>
                  <td style={{ color: "var(--text-muted)" }}>{d.contributing_factors?.length || 0} factors</td>
                  <td>
                    <button 
                        className="btn btn-secondary btn-sm" 
                        style={{ display: 'flex', alignItems: 'center', gap: 4, padding: "6px 10px" }} 
                        onClick={(e) => {
                            e.stopPropagation();
                            setExpandedId(expandedId === d.distributor_id ? null : d.distributor_id);
                        }}
                    >
                      {expandedId === d.distributor_id ? <><ChevronUp size={14}/> Hide Details</> : <><ChevronDown size={14}/> View Details</>}
                    </button>
                  </td>
                </tr>
                <AnimatePresence>
                    {expandedId === d.distributor_id && (
                    <tr>
                        <td colSpan={5} style={{ padding: 0, borderBottom: "1px solid var(--border-color)", background: "var(--bg-hover)" }}>
                        <DistributorDetail id={d.distributor_id} />
                        </td>
                    </tr>
                    )}
                </AnimatePresence>
              </React.Fragment>
            ))}
            {distributors.length === 0 && (
              <tr>
                <td colSpan={5} style={{ textAlign: "center", color: "var(--text-muted)", padding: 40 }}>No distributors found.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab 2: Batch Collisions
// ---------------------------------------------------------------------------
function BatchCollisionsTab() {
  const [collisions, setCollisions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getBatchCollisions(365)
      .then((data) => setCollisions(data || []))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>Loading batch collisions...</div>;

  if (collisions.length === 0) return (
      <div style={{ textAlign: "center", padding: "40px 20px", background: "var(--bg-surface)", borderRadius: 8, border: "1px dashed var(--border-color)" }}>
          <ShieldCheck size={40} style={{ color: "var(--success-500)", marginBottom: 12, opacity: 0.8 }} />
          <p style={{ margin: 0, color: "var(--text-muted)", fontSize: 16 }}>No batch collisions found in the last 365 days.</p>
      </div>
  );

  return (
    <div style={{ display: "grid", gap: 16 }}>
      {collisions.map((c, i) => (
        <div key={i} className="card" style={{ marginBottom: 0, borderLeft: "4px solid var(--danger-500)" }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
            <h4 style={{ margin: 0, color: "var(--text-main)", fontSize: 18, display: 'flex', alignItems: 'center', gap: 8 }}>
                {c.medicine_name}
            </h4>
            <span className="badge badge-danger" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <ShieldAlert size={14} /> Collision Detected
            </span>
          </div>
          <div style={{ marginTop: 16, fontSize: 14, color: "var(--text-main)", display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
            <div style={{ background: 'var(--bg-hover)', padding: '10px 12px', borderRadius: 6 }}>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 2 }}>Normalized Batch</div>
                <div style={{ fontWeight: 600 }}>{c.normalized_batch_number}</div>
            </div>
            <div style={{ background: 'var(--bg-hover)', padding: '10px 12px', borderRadius: 6 }}>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 2 }}>Distributors Involved</div>
                <div style={{ fontWeight: 600 }}>{c.distributor_names?.join(" & ") || "Unknown"}</div>
            </div>
            <div style={{ background: 'var(--bg-hover)', padding: '10px 12px', borderRadius: 6 }}>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 2 }}>Occurrences</div>
                <div style={{ fontWeight: 600 }}>{c.occurrence_count} times</div>
            </div>
            {c.date_range && (
                <div style={{ background: 'var(--bg-hover)', padding: '10px 12px', borderRadius: 6 }}>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 2 }}>Date Range</div>
                    <div style={{ fontWeight: 600 }}>{c.date_range.start} to {c.date_range.end}</div>
                </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

export default function TrustScore() {
  const [tab, setTab] = useState("scores");
  const [showCopilot, setShowCopilot] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      setShowCopilot(true);
    }, 10000);
    return () => clearTimeout(timer);
  }, []);

  return (
    <motion.div 
      className="page-content"
      initial={{ opacity: 0, y: 10 }} 
      animate={{ opacity: 1, y: 0 }} 
      exit={{ opacity: 0, y: -10 }} 
      transition={{ duration: 0.2 }}
    >
      <div className="card" style={{ marginBottom: 24 }}>
        <h2 style={{ margin: "0 0 8px 0", color: "var(--text-main)", display: "flex", alignItems: "center", gap: 10 }}>
            <Shield size={28} style={{ color: "var(--primary-500)" }} /> Supply Chain Trust Score
        </h2>
        <p style={{ color: "var(--text-muted)", fontSize: 14, margin: "0 0 20px 0", lineHeight: 1.5, maxWidth: "800px" }}>
          Composite trust scoring based on historical purchasing patterns, rate consistency, and batch collisions. 
          Use this to evaluate the reliability and integrity of your supply chain partners.
        </p>
        <div style={{ display: "flex", gap: 8, borderBottom: "1px solid var(--border-color)", paddingBottom: 12 }}>
          <button 
            className="btn" 
            style={{ background: tab === "scores" ? "var(--primary-50)" : "transparent", color: tab === "scores" ? "var(--primary-500)" : "var(--text-muted)", border: "none", padding: "8px 16px", fontWeight: 500 }} 
            onClick={() => setTab("scores")}
          >
            Trust Scores
          </button>
          <button 
            className="btn" 
            style={{ background: tab === "collisions" ? "var(--primary-50)" : "transparent", color: tab === "collisions" ? "var(--primary-500)" : "var(--text-muted)", border: "none", padding: "8px 16px", fontWeight: 500 }} 
            onClick={() => setTab("collisions")}
          >
            Batch Collisions
          </button>
        </div>
      </div>

      <AnimatePresence mode="wait">
        <motion.div
            key={tab}
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -5 }}
            transition={{ duration: 0.15 }}
        >
            {tab === "scores" && <TrustScoresTab />}
            {tab === "collisions" && <BatchCollisionsTab />}
        </motion.div>
      </AnimatePresence>

      {/* Proactive Copilot Bubble */}
      <AnimatePresence>
        {showCopilot && (
          <motion.div
            initial={{ opacity: 0, y: 50, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 50, scale: 0.9 }}
            transition={{ type: "spring", stiffness: 300, damping: 25 }}
            style={{
              position: "fixed", bottom: 40, right: 40, zIndex: 9999,
              display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 12
            }}
          >
            <div style={{
              background: "var(--bg-surface)", padding: "16px 20px", borderRadius: "16px 16px 4px 16px",
              boxShadow: "0 20px 40px rgba(0,0,0,0.2)", border: "1px solid var(--border-subtle)",
              maxWidth: 250, position: "relative"
            }}>
              <button 
                onClick={() => setShowCopilot(false)} 
                style={{ position: "absolute", top: 8, right: 8, background: "transparent", border: "none", cursor: "pointer", color: "var(--text-muted)" }}
              >
                <X size={14} />
              </button>
              <p style={{ margin: "0 0 12px 0", fontSize: "14px", color: "var(--text-main)", fontWeight: 500, paddingRight: 16 }}>
                Need help understanding these trust scores and anomalies?
              </p>
              <Link to="/copilot" style={{ textDecoration: "none" }}>
                <button className="btn btn-primary" style={{ width: "100%", padding: "6px 12px", fontSize: "13px" }}>
                  Ask Copilot
                </button>
              </Link>
            </div>
            <Link to="/copilot" style={{ textDecoration: "none" }}>
              <motion.div 
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.9 }}
                style={{
                  width: 56, height: 56, borderRadius: "50%", background: "var(--primary-600)",
                  display: "flex", alignItems: "center", justifyContent: "center", color: "white",
                  boxShadow: "0 10px 20px rgba(20, 184, 166, 0.3)", cursor: "pointer"
                }}
              >
                <BotMessageSquare size={28} />
              </motion.div>
            </Link>
          </motion.div>
        )}
      </AnimatePresence>

      <style>{`
        .trust-table { width: 100%; border-collapse: collapse; }
        .trust-table th, .trust-table td { text-align: left; padding: 14px 12px; border-bottom: 1px solid var(--border-color); }
        .trust-table th { color: var(--text-muted); font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; background: var(--bg-surface); }
        .trust-table tr { transition: background 0.2s; }
        .trust-table tr:hover:not(.expanded-row-parent) { background: var(--bg-hover); }
        .trust-table tr.expanded-row-parent { background: var(--bg-hover); }
        
        .trust-detail-pane { padding: 20px; margin: 0; background: var(--bg-hover); overflow: hidden; }
        .trust-detail-pane h4 { margin: 0 0 12px 0; color: var(--text-main); font-size: 15px; font-weight: 600; }
      `}</style>
    </motion.div>
  );
}
