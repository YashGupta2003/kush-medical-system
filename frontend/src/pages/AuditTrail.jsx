import { useEffect, useState, useRef } from "react";
import { api } from "../api/client.js";
import { 
  Link as LinkIcon, CheckCircle2, AlertTriangle, FileText, 
  Package, Activity, Shield, ShieldCheck, Database, 
  Lock, ArrowRight, ChevronRight, ChevronDown, Check, XCircle
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

const EVENT_META = {
  rate_change: { label: "Rate change", icon: <Activity size={14} />, badge: "auto" },
  batch_received: { label: "Batch received", icon: <Package size={14} />, badge: "learned" },
  bill_confirmed: { label: "Bill confirmed", icon: <FileText size={14} />, badge: "manual" },
  stock_adjustment: { label: "Stock adjustment", icon: <Database size={14} />, badge: "unmatched" },
};

function eventMeta(type) {
  return EVENT_META[type] || { label: type, icon: <LinkIcon size={14} />, badge: "manual" };
}

function shortHash(h) {
  if (!h) return "—";
  return `${h.slice(0, 8)}…${h.slice(-6)}`;
}

function timeAgo(iso) {
  if (!iso) return "—";
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function payloadSummary(entry) {
  const p = entry.payload || {};
  switch (entry.event_type) {
    case "rate_change":
      return `${p.medicine_name || "ID: " + p.medicine_id} • ₹${p.old_net_rate ?? "—"} → ₹${p.new_net_rate ?? "—"}`;
    case "batch_received":
      return `${p.qty_received ?? "—"} units${p.batch_no ? ` • batch ${p.batch_no}` : ""}${p.expiry_date ? ` • exp ${p.expiry_date}` : ""}`;
    case "bill_confirmed":
      return `Bill #${p.bill_id} • ${p.item_count ?? "—"} items • ₹${p.total_amount ?? "—"}${p.invoice_no ? ` • Inv ${p.invoice_no}` : ""}`;
    case "stock_adjustment":
      return `${p.medicine_name || "ID: " + p.medicine_id} • ${p.previous_stock ?? "—"} → ${p.new_stock ?? "—"}`;
    default:
      return JSON.stringify(p).slice(0, 80);
  }
}

// ---------------------------------------------------------------------------
// VerifyBanner with sequential scanning animation
// ---------------------------------------------------------------------------
function VerifyBanner({ result, verifying, onVerify }) {
  const [scanProgress, setScanProgress] = useState(0);

  useEffect(() => {
    let interval;
    if (verifying) {
      setScanProgress(0);
      interval = setInterval(() => {
        setScanProgress((prev) => {
          if (prev >= 98) return prev;
          return prev + Math.random() * 5;
        });
      }, 50);
    } else {
      setScanProgress(100);
    }
    return () => clearInterval(interval);
  }, [verifying]);

  const isValid = result && result.is_valid;
  const isBroken = result && !result.is_valid;

  let bgClass = "var(--bg-surface)";
  let borderColor = "var(--border-subtle)";
  let textColor = "var(--text-main)";
  let Icon = Shield;
  let iconColor = "var(--text-muted)";
  
  if (verifying) {
    bgClass = "var(--primary-50)";
    borderColor = "var(--primary-200)";
    textColor = "var(--primary-700)";
    Icon = Activity;
    iconColor = "var(--primary-500)";
  } else if (isValid) {
    bgClass = "var(--success-bg)";
    borderColor = "var(--success-border)";
    textColor = "var(--success-text)";
    Icon = ShieldCheck;
    iconColor = "var(--success-text)";
  } else if (isBroken) {
    bgClass = "var(--danger-bg)";
    borderColor = "var(--danger-border)";
    textColor = "var(--danger-text)";
    Icon = ShieldAlert;
    iconColor = "var(--danger-text)";
  }

  return (
    <div style={{
      position: "relative",
      display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16,
      padding: "var(--space-6)", borderRadius: "var(--radius-xl)", border: `1px solid ${borderColor}`,
      background: bgClass, transition: "all 0.3s ease", overflow: "hidden"
    }}>
      {/* Scanning Laser Effect */}
      {verifying && (
        <motion.div 
          style={{ position: "absolute", top: 0, bottom: 0, left: 0, width: "100%", background: "linear-gradient(90deg, transparent, rgba(20, 184, 166, 0.2), transparent)", zIndex: 0 }}
          animate={{ x: ["-100%", "100%"] }}
          transition={{ repeat: Infinity, duration: 1.5, ease: "linear" }}
        />
      )}
      
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-4)", position: "relative", zIndex: 1 }}>
        <div style={{ 
          width: 48, height: 48, borderRadius: "var(--radius-full)", background: "var(--bg-app)", 
          display: "flex", alignItems: "center", justifyContent: "center", color: iconColor, border: `1px solid ${borderColor}`
        }}>
          <Icon size={24} style={{ animation: verifying ? "pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite" : "none" }} />
        </div>
        
        <div style={{ color: textColor }}>
          {!result && !verifying && (
            <>
              <div style={{ fontWeight: 700, fontSize: "var(--text-lg)" }}>Cryptographic Ledger Idle</div>
              <div style={{ fontSize: "var(--text-sm)", opacity: 0.8, marginTop: 4 }}>
                Ready to recompute all blocks from genesis to prove immutability.
              </div>
            </>
          )}
          {verifying && (
            <>
              <div style={{ fontWeight: 700, fontSize: "var(--text-lg)" }}>Verifying TrustChain...</div>
              <div style={{ fontSize: "var(--text-sm)", opacity: 0.8, marginTop: 4 }}>
                Recomputing SHA-256 hashes. Progress: {Math.round(scanProgress)}%
              </div>
            </>
          )}
          {isValid && (
            <>
              <div style={{ fontWeight: 700, fontSize: "var(--text-lg)", display: "flex", alignItems: "center", gap: 6 }}><CheckCircle2 size={18} /> Chain Verified — Unbroken</div>
              <div style={{ fontSize: "var(--text-sm)", opacity: 0.8, marginTop: 4 }}>
                All {result.total_entries} blocks verified flawlessly at {new Date(result.verified_at).toLocaleTimeString()}.
              </div>
            </>
          )}
          {isBroken && (
            <>
              <div style={{ fontWeight: 700, fontSize: "var(--text-lg)", display: "flex", alignItems: "center", gap: 6 }}><AlertTriangle size={18} /> Integrity Violation Detected</div>
              <div style={{ fontSize: "var(--text-sm)", opacity: 0.8, marginTop: 4 }}>
                {result.broken_entries.length} block(s) tampered out of {result.total_entries}. Details below.
              </div>
            </>
          )}
        </div>
      </div>
      
      <div style={{ position: "relative", zIndex: 1 }}>
        <button 
          className="btn btn-primary" 
          onClick={onVerify} 
          disabled={verifying}
          style={{ padding: "var(--space-3) var(--space-6)", fontSize: "var(--text-base)" }}
        >
          {verifying ? "Computing..." : "Run Cryptographic Audit"}
        </button>
      </div>
    </div>
  );
}

function BrokenEntriesList({ entries }) {
  if (!entries || entries.length === 0) return null;
  return (
    <div style={{ marginTop: "var(--space-4)", display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
      {entries.map((b) => (
        <motion.div key={b.id} initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} style={{
          background: "var(--bg-app)", border: "1px solid var(--danger-border)", borderLeft: "4px solid var(--danger-text)",
          borderRadius: "var(--radius-md)", padding: "var(--space-4)"
        }}>
          <div className="flex-between" style={{ marginBottom: "var(--space-2)" }}>
            <strong style={{ fontSize: "var(--text-sm)", display: "flex", alignItems: "center", gap: 6, color: "var(--text-main)" }}>
              <XCircle size={14} color="var(--danger-text)" /> Block #{b.id} • {eventMeta(b.event_type).label}
              {b.reference_id != null && <span style={{ color: "var(--text-muted)", fontWeight: 400 }}> (ref #{b.reference_id})</span>}
            </strong>
            <span style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>{b.created_at ? new Date(b.created_at).toLocaleString() : ""}</span>
          </div>
          <ul style={{ margin: 0, paddingLeft: 22, fontSize: "var(--text-xs)", color: "var(--danger-text)" }}>
            {b.problems.map((p, i) => <li key={i} style={{ marginBottom: 4 }}>{p}</li>)}
          </ul>
        </motion.div>
      ))}
    </div>
  );
}

function LedgerRow({ entry, isBroken }) {
  const [expanded, setExpanded] = useState(false);
  const meta = eventMeta(entry.event_type);

  return (
    <div style={{ borderBottom: "1px solid var(--border-subtle)", background: isBroken ? "var(--danger-bg)" : "transparent" }}>
      <div 
        onClick={() => setExpanded((e) => !e)}
        style={{ 
          display: "flex", alignItems: "center", gap: "var(--space-3)", padding: "var(--space-3) var(--space-4)", 
          cursor: "pointer", transition: "background 0.2s" 
        }}
        onMouseEnter={(e) => e.currentTarget.style.background = "var(--bg-surface-hover)"}
        onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
      >
        <span style={{ color: "var(--text-muted)", display: "flex" }}>
          {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </span>
        <span className={`badge ${meta.badge}`} style={{ flexShrink: 0, display: "flex", alignItems: "center", gap: 6 }}>
          {meta.icon} {meta.label}
        </span>
        <span style={{ flex: 1, fontSize: "var(--text-sm)", color: "var(--text-main)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {payloadSummary(entry)}
        </span>
        <span style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)", flexShrink: 0 }} title={new Date(entry.created_at).toLocaleString()}>
          {timeAgo(entry.created_at)}
        </span>
      </div>

      <AnimatePresence>
        {expanded && (
          <motion.div 
            initial={{ opacity: 0, height: 0 }} 
            animate={{ opacity: 1, height: "auto" }} 
            exit={{ opacity: 0, height: 0 }}
            style={{ overflow: "hidden" }}
          >
            <div style={{ padding: "0 var(--space-4) var(--space-4) 44px" }}>
              {/* Hash Chain Visualizer */}
              <div style={{ 
                display: "flex", alignItems: "center", gap: "var(--space-2)", flexWrap: "wrap",
                background: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-lg)", 
                padding: "var(--space-3) var(--space-4)", marginBottom: "var(--space-3)" 
              }}>
                <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  <div style={{ fontSize: 10, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: 600 }}>Previous Hash</div>
                  <code style={{ fontFamily: "ui-monospace, monospace", fontSize: 12, background: "var(--bg-app)", padding: "4px 8px", borderRadius: 4, color: "var(--text-main)" }}>
                    {shortHash(entry.previous_hash)}
                  </code>
                </div>
                
                <div style={{ display: "flex", alignItems: "center", color: "var(--text-muted)" }}>
                  <span style={{ margin: "0 8px" }}>+</span>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  <div style={{ fontSize: 10, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: 600 }}>Payload Hash</div>
                  <code style={{ fontFamily: "ui-monospace, monospace", fontSize: 12, background: "var(--bg-app)", padding: "4px 8px", borderRadius: 4, color: "var(--text-main)" }}>
                    {shortHash(entry.payload_hash)}
                  </code>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--primary-500)", margin: "0 8px" }}>
                  <ArrowRight size={14} /> <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: 1 }}>SHA-256</span> <ArrowRight size={14} />
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  <div style={{ fontSize: 10, color: "var(--primary-200)", textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: 600 }}>Entry Block Hash</div>
                  <code style={{ fontFamily: "ui-monospace, monospace", fontSize: 12, background: "var(--primary-700)", color: "#fff", padding: "4px 8px", borderRadius: 4, border: "1px solid var(--primary-600)" }}>
                    {shortHash(entry.entry_hash)}
                  </code>
                </div>
              </div>

              {/* JSON Payload */}
              <div style={{ background: "#0d0d12", borderRadius: "var(--radius-lg)", padding: "var(--space-4)", border: "1px solid #1f1f2e" }}>
                <div style={{ fontSize: 10, color: "#8a8a9e", textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: 600, marginBottom: "var(--space-2)" }}>Raw Block Payload</div>
                <pre style={{ margin: 0, color: "#10b981", fontSize: 12, fontFamily: "ui-monospace, monospace", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                  {JSON.stringify(entry.payload, null, 2)}
                </pre>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function AuditTrail() {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [eventType, setEventType] = useState("");
  const [verifyResult, setVerifyResult] = useState(null);
  const [verifying, setVerifying] = useState(false);
  const [error, setError] = useState(null);

  function refresh() {
    setLoading(true);
    api.getAuditLedger({ event_type: eventType || undefined, limit: 150 })
      .then(setEntries)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => { refresh(); /* eslint-disable-next-line */ }, [eventType]);

  async function handleVerify() {
    setVerifying(true);
    setError(null);
    try {
      // Small artificial delay to let the animation play out for dramatic effect
      await new Promise(resolve => setTimeout(resolve, 1500));
      const res = await api.verifyAuditChain();
      setVerifyResult(res);
    } catch (e) {
      setError(e.message);
    } finally {
      setVerifying(false);
    }
  }

  const brokenIds = new Set((verifyResult?.broken_entries || []).map((b) => b.id));
  const counts = entries.reduce((acc, e) => { acc[e.event_type] = (acc[e.event_type] || 0) + 1; return acc; }, {});

  return (
    <div style={{ paddingBottom: "var(--space-10)" }}>
      <div className="card" style={{ marginBottom: "var(--space-6)" }}>
        <h1 style={{ display: "flex", alignItems: "center", gap: 12, fontSize: "var(--text-3xl)", marginBottom: "var(--space-2)" }}>
          <Lock size={32} color="var(--primary-500)" /> TrustChain Ledger
        </h1>
        <p style={{ color: "var(--text-muted)", fontSize: "var(--text-base)", marginBottom: "var(--space-6)", maxWidth: 800 }}>
          An append-only cryptographic ledger. Every significant operational event is chained, deriving its SHA-256 hash from the previous block back to genesis. Any database-level tampering breaks the cryptographic link permanently.
        </p>

        <div style={{ display: "flex", gap: "var(--space-4)", flexWrap: "wrap", padding: "var(--space-4)", background: "var(--bg-app)", borderRadius: "var(--radius-lg)", border: "1px solid var(--border-subtle)" }}>
          <div className="stat-card" style={{ flex: 1, minWidth: 150 }}>
            <span className="stat-label">Total Chain Blocks</span>
            <span className="stat-value">{entries.length}</span>
          </div>
          {Object.entries(EVENT_META).map(([key, meta]) => (
            <div key={key} className="stat-card" style={{ flex: 1, minWidth: 150 }}>
              <span className="stat-label" style={{ display: "flex", alignItems: "center", gap: 6 }}>{meta.icon} {meta.label}</span>
              <span className="stat-value">{counts[key] || 0}</span>
            </div>
          ))}
        </div>
      </div>

      <div style={{ marginBottom: "var(--space-6)" }}>
        <VerifyBanner result={verifyResult} verifying={verifying} onVerify={handleVerify} />
        {verifyResult && !verifyResult.is_valid && <BrokenEntriesList entries={verifyResult.broken_entries} />}
        {error && <div style={{ color: "var(--danger-text)", fontSize: "var(--text-sm)", marginTop: "var(--space-3)", padding: "var(--space-3)", background: "var(--danger-bg)", borderRadius: "var(--radius-md)" }}>{error}</div>}
      </div>

      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        <div className="flex-between" style={{ padding: "var(--space-4)", borderBottom: "1px solid var(--border-subtle)", background: "var(--bg-surface)" }}>
          <h3 style={{ margin: 0, fontSize: "var(--text-lg)", display: "flex", alignItems: "center", gap: 8 }}>
            <Database size={18} /> Block Explorer
          </h3>
          <select className="input" style={{ width: 220, padding: "var(--space-2)" }} value={eventType} onChange={(e) => setEventType(e.target.value)}>
            <option value="">All Block Types</option>
            {Object.entries(EVENT_META).map(([key, meta]) => (
              <option key={key} value={key}>{meta.label}</option>
            ))}
          </select>
        </div>

        {loading && (
          <div style={{ padding: "var(--space-8)", textAlign: "center", color: "var(--text-muted)" }}>
            <Activity size={24} style={{ animation: "spin 2s linear infinite", margin: "0 auto var(--space-3)" }} />
            <p>Syncing ledger...</p>
          </div>
        )}

        {!loading && entries.length === 0 && (
          <div className="empty-state" style={{ padding: "var(--space-10)" }}>
            <Database size={32} className="empty-state-icon" />
            <p style={{ margin: 0, color: "var(--text-muted)" }}>Genesis block pending. The ledger will append as operational events occur.</p>
          </div>
        )}

        {!loading && (
          <div style={{ display: "flex", flexDirection: "column" }}>
            {entries.map((entry) => (
              <LedgerRow key={entry.id} entry={entry} isBroken={brokenIds.has(entry.id)} />
            ))}
          </div>
        )}
      </div>

      <style>{`
        @keyframes spin { 100% { transform: rotate(360deg); } }
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: .5; }
        }
      `}</style>
    </div>
  );
}