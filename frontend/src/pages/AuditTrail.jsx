import { useEffect, useState } from "react";
import { api } from "../api/client.js";

const EVENT_META = {
  rate_change: { label: "Rate change", icon: "💰", badge: "auto" },
  batch_received: { label: "Batch received", icon: "📦", badge: "learned" },
  bill_confirmed: { label: "Bill confirmed", icon: "🧾", badge: "manual" },
  stock_adjustment: { label: "Stock adjustment", icon: "⚖️", badge: "unmatched" },
};

function eventMeta(type) {
  return EVENT_META[type] || { label: type, icon: "🔗", badge: "manual" };
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

// ---------------------------------------------------------------------------
// Payload summary — a tiny, event-type-aware one-liner so the table is
// scannable without expanding every row.
// ---------------------------------------------------------------------------
function payloadSummary(entry) {
  const p = entry.payload || {};
  switch (entry.event_type) {
    case "rate_change":
      return `${p.medicine_name || "Medicine #" + p.medicine_id} · ₹${p.old_net_rate ?? "—"} → ₹${p.new_net_rate ?? "—"}`;
    case "batch_received":
      return `${p.qty_received ?? "—"} units${p.batch_no ? ` · batch ${p.batch_no}` : ""}${p.expiry_date ? ` · exp ${p.expiry_date}` : ""}`;
    case "bill_confirmed":
      return `Bill #${p.bill_id} · ${p.item_count ?? "—"} items · ₹${p.total_amount ?? "—"}${p.invoice_no ? ` · Inv ${p.invoice_no}` : ""}`;
    case "stock_adjustment":
      return `${p.medicine_name || "Medicine #" + p.medicine_id} · ${p.previous_stock ?? "—"} → ${p.new_stock ?? "—"}`;
    default:
      return JSON.stringify(p).slice(0, 80);
  }
}

// ---------------------------------------------------------------------------
// Verify-chain result banner
// ---------------------------------------------------------------------------
function VerifyBanner({ result, verifying, onVerify }) {
  return (
    <div className={`audit-verify-banner ${result ? (result.is_valid ? "valid" : "broken") : "idle"}`}>
      <div className="audit-verify-left">
        <span className="audit-verify-icon">
          {!result ? "🔗" : result.is_valid ? "✅" : "🚨"}
        </span>
        <div>
          {!result && (
            <>
              <div className="audit-verify-title">Chain integrity: not yet checked</div>
              <div className="audit-verify-sub">
                Recomputes every hash in the ledger from scratch and confirms nothing has been altered.
              </div>
            </>
          )}
          {result && result.is_valid && (
            <>
              <div className="audit-verify-title">Chain verified — unbroken from genesis</div>
              <div className="audit-verify-sub">
                All {result.total_entries} entries recomputed cleanly. Checked {timeAgo(result.verified_at)}.
              </div>
            </>
          )}
          {result && !result.is_valid && (
            <>
              <div className="audit-verify-title">Tampering detected — {result.broken_entries.length} entry(ies) broken</div>
              <div className="audit-verify-sub">
                Out of {result.total_entries} total entries. See below for exactly what changed.
              </div>
            </>
          )}
        </div>
      </div>
      <button onClick={onVerify} disabled={verifying}>
        {verifying ? "Verifying..." : "Verify chain integrity"}
      </button>
    </div>
  );
}

function BrokenEntriesList({ entries }) {
  if (!entries || entries.length === 0) return null;
  return (
    <div className="audit-broken-list">
      {entries.map((b) => (
        <div key={b.id} className="audit-broken-row">
          <div className="flex-between">
            <strong style={{ fontSize: 13 }}>
              {eventMeta(b.event_type).icon} Entry #{b.id} · {eventMeta(b.event_type).label}
              {b.reference_id != null && <span style={{ color: "#888", fontWeight: 400 }}> (ref #{b.reference_id})</span>}
            </strong>
            <span style={{ fontSize: 11, color: "#888" }}>{b.created_at ? new Date(b.created_at).toLocaleString() : ""}</span>
          </div>
          <ul className="audit-broken-problems">
            {b.problems.map((p, i) => <li key={i}>{p}</li>)}
          </ul>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// One ledger row, expandable to show the actual hash chain values — this
// is what makes "how does tamper-evidence actually work" demonstrable
// rather than just asserted.
// ---------------------------------------------------------------------------
function LedgerRow({ entry, isBroken }) {
  const [expanded, setExpanded] = useState(false);
  const meta = eventMeta(entry.event_type);

  return (
    <div className={`audit-ledger-row ${isBroken ? "broken" : ""}`}>
      <div className="audit-ledger-row-summary" onClick={() => setExpanded((e) => !e)}>
        <span className="audit-ledger-caret">{expanded ? "▾" : "▸"}</span>
        <span className={`badge ${meta.badge}`} style={{ flexShrink: 0 }}>{meta.icon} {meta.label}</span>
        <span className="audit-ledger-summary-text">{payloadSummary(entry)}</span>
        <span className="audit-ledger-time" title={new Date(entry.created_at).toLocaleString()}>
          {timeAgo(entry.created_at)}
        </span>
      </div>

      {expanded && (
        <div className="audit-ledger-detail">
          <div className="audit-hash-chain">
            <div className="audit-hash-block">
              <div className="audit-hash-label">previous_hash</div>
              <code className="audit-hash-value">{shortHash(entry.previous_hash)}</code>
            </div>
            <span className="audit-hash-arrow">＋</span>
            <div className="audit-hash-block">
              <div className="audit-hash-label">payload_hash</div>
              <code className="audit-hash-value">{shortHash(entry.payload_hash)}</code>
            </div>
            <span className="audit-hash-arrow">→ SHA-256 →</span>
            <div className="audit-hash-block current">
              <div className="audit-hash-label">entry_hash</div>
              <code className="audit-hash-value">{shortHash(entry.entry_hash)}</code>
            </div>
          </div>
          <div className="audit-payload-json">
            <div className="audit-hash-label" style={{ marginBottom: 4 }}>Full payload (what was hashed)</div>
            <pre>{JSON.stringify(entry.payload, null, 2)}</pre>
          </div>
        </div>
      )}
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
    <div>
      <div className="card audit-header-card">
        <h2 style={{ marginBottom: 4 }}>🔗 TrustChain — Tamper-Evident Audit Trail</h2>
        <p style={{ color: "#666", fontSize: 13, marginTop: 0, maxWidth: 760 }}>
          Every rate change, batch receipt, confirmed bill, and manual stock adjustment is chained
          into an append-only ledger — each entry's hash is derived from the entry before it, all
          the way back to genesis. Editing any past entry (even directly in the database) breaks
          the chain from that point forward, and <strong>Verify chain integrity</strong> below
          proves it. This is a hash chain, not a distributed blockchain — deliberately, since a
          single shop's database has one trust boundary and doesn't need a multi-party consensus
          network to get tamper-evidence.
        </p>

        <div className="stat-row" style={{ marginTop: 14, marginBottom: 0 }}>
          <div className="stat-box">
            <div className="value">{entries.length}</div>
            <div className="label">Entries shown</div>
          </div>
          {Object.entries(EVENT_META).map(([key, meta]) => (
            <div key={key} className="stat-box">
              <div className="value">{counts[key] || 0}</div>
              <div className="label">{meta.icon} {meta.label}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <VerifyBanner result={verifyResult} verifying={verifying} onVerify={handleVerify} />
        {verifyResult && !verifyResult.is_valid && <BrokenEntriesList entries={verifyResult.broken_entries} />}
        {error && <p style={{ color: "#b91c1c", fontSize: 13, marginTop: 10 }}>{error}</p>}
      </div>

      <div className="card">
        <div className="flex-between" style={{ marginBottom: 10 }}>
          <h3 style={{ margin: 0 }}>Ledger</h3>
          <select value={eventType} onChange={(e) => setEventType(e.target.value)}>
            <option value="">All event types</option>
            {Object.entries(EVENT_META).map(([key, meta]) => (
              <option key={key} value={key}>{meta.icon} {meta.label}</option>
            ))}
          </select>
        </div>

        {loading && <p style={{ color: "#888", fontSize: 13 }}>Loading ledger...</p>}

        {!loading && entries.length === 0 && (
          <p style={{ color: "#888", fontSize: 13 }}>
            No audit entries yet — they're created automatically as bills are confirmed, batches
            are received, rates change, and stock is manually adjusted.
          </p>
        )}

        {!loading && entries.map((entry) => (
          <LedgerRow key={entry.id} entry={entry} isBroken={brokenIds.has(entry.id)} />
        ))}
      </div>

      <style>{`
        .audit-header-card { background: linear-gradient(135deg, #fff, #f8faff); }

        .audit-verify-banner {
          display: flex; justify-content: space-between; align-items: center; gap: 16px;
          padding: 16px 18px; border-radius: 12px; border: 1px solid #e5e5e5; background: #fafafa;
          transition: background 0.2s ease, border-color 0.2s ease;
        }
        .audit-verify-banner.valid { background: #f0fdf4; border-color: #bbf7d0; }
        .audit-verify-banner.broken { background: #fef2f2; border-color: #fecaca; }
        .audit-verify-left { display: flex; align-items: center; gap: 12px; }
        .audit-verify-icon { font-size: 26px; flex-shrink: 0; }
        .audit-verify-title { font-weight: 700; font-size: 14.5px; color: #1c1c1e; }
        .audit-verify-sub { font-size: 12.5px; color: #666; margin-top: 2px; }

        .audit-broken-list { margin-top: 14px; display: flex; flex-direction: column; gap: 10px; }
        .audit-broken-row {
          background: #fff; border: 1px solid #fecaca; border-left: 4px solid #dc2626;
          border-radius: 10px; padding: 12px 14px;
        }
        .audit-broken-problems { margin: 8px 0 0; padding-left: 18px; font-size: 12.5px; color: #7f1d1d; }
        .audit-broken-problems li { margin-bottom: 3px; }

        .audit-ledger-row {
          border-bottom: 1px solid #f0f0f0;
        }
        .audit-ledger-row:last-child { border-bottom: none; }
        .audit-ledger-row.broken { background: #fff5f5; }
        .audit-ledger-row-summary {
          display: flex; align-items: center; gap: 10px; padding: 11px 4px; cursor: pointer;
          transition: background 0.12s ease;
        }
        .audit-ledger-row-summary:hover { background: #fafafa; }
        .audit-ledger-caret { width: 12px; color: #999; font-size: 11px; flex-shrink: 0; }
        .audit-ledger-summary-text { flex: 1; font-size: 13px; color: #333; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .audit-ledger-time { font-size: 11.5px; color: #999; flex-shrink: 0; }

        .audit-ledger-detail {
          padding: 4px 4px 16px 26px; animation: auditFadeIn 0.2s ease;
        }
        @keyframes auditFadeIn { from { opacity: 0; } to { opacity: 1; } }

        .audit-hash-chain {
          display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
          background: #f8f9fb; border: 1px solid #eee; border-radius: 10px; padding: 12px 14px;
          margin-bottom: 10px;
        }
        .audit-hash-block { display: flex; flex-direction: column; gap: 2px; }
        .audit-hash-block.current .audit-hash-value { background: #1c1c1e; color: #fff; }
        .audit-hash-label { font-size: 10px; color: #999; text-transform: uppercase; letter-spacing: 0.4px; }
        .audit-hash-value {
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px;
          background: #eee; padding: 3px 8px; border-radius: 6px; color: #1c1c1e;
        }
        .audit-hash-arrow { color: #aaa; font-size: 12px; }

        .audit-payload-json {
          background: #1c1c1e; border-radius: 10px; padding: 12px 14px;
        }
        .audit-payload-json .audit-hash-label { color: #999; }
        .audit-payload-json pre {
          margin: 0; color: #d1f5d3; font-size: 12px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          white-space: pre-wrap; word-break: break-word;
        }
      `}</style>
    </div>
  );
}