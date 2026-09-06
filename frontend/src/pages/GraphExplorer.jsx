import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Network, FlaskConical, AlertTriangle, Pill, Repeat, Building, Search, RefreshCw } from "lucide-react";
import { api } from "../api/client.js";

const SEVERITY_META = {
  high: { color: "var(--danger-700)", bg: "var(--danger-100)", label: "High risk" },
  medium: { color: "var(--warning-700)", bg: "var(--warning-100)", label: "Medium risk" },
  low: { color: "var(--info-700)", bg: "var(--info-100)", label: "Low risk" },
  unknown: { color: "var(--text-secondary)", bg: "var(--bg-muted)", label: "Flagged" },
};

function Section({ icon, title, count, children, emptyText }) {
  return (
    <div className="card graph-section" style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div className="flex-between" style={{ marginBottom: "16px", paddingBottom: "12px", borderBottom: "1px solid var(--border-color)" }}>
        <h3 style={{ margin: 0, fontSize: "15px", display: "flex", alignItems: "center", gap: "8px", color: "var(--text-main)" }}>
          {icon} {title}
        </h3>
        <span style={{ fontSize: "12px", color: "var(--text-muted)", background: "var(--bg-muted)", padding: "2px 8px", borderRadius: "12px", fontWeight: 600 }}>{count}</span>
      </div>
      <div style={{ flex: 1 }}>
        {count === 0 ? (
          <p style={{ color: "var(--text-muted)", fontSize: "13px", margin: 0, fontStyle: "italic" }}>{emptyText}</p>
        ) : children}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Medicine search box - picks the medicine whose graph to explore.
// ---------------------------------------------------------------------------
function MedicinePicker({ onSelect }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);

  useEffect(() => {
    if (query.trim().length < 2) { setResults([]); return; }
    const t = setTimeout(() => {
      api.browseMedicines({ q: query, page: 1, page_size: 8 }).then((d) => setResults(d.items));
    }, 250);
    return () => clearTimeout(t);
  }, [query]);

  return (
    <div className="card" style={{ display: "flex", gap: "16px", alignItems: "flex-start" }}>
      <div style={{ background: "var(--primary-100)", padding: "12px", borderRadius: "12px" }}>
        <Network size={28} color="var(--primary-600)" />
      </div>
      <div style={{ flex: 1 }}>
        <h2 style={{ margin: "0 0 4px 0", color: "var(--text-main)" }}>PharmaGraph Explorer</h2>
        <p style={{ color: "var(--text-secondary)", fontSize: "13px", margin: "0 0 16px 0", lineHeight: 1.5 }}>
          Search any medicine to see its full relationship graph — what salts it contains, what
          those salts interact with, what conditions they treat, which medicines can substitute
          for it, and which distributors have supplied it.
        </p>
        <div style={{ position: "relative" }}>
          <Search size={16} style={{ position: "absolute", left: "12px", top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }} />
          <input
            style={{ width: "100%", paddingLeft: "36px" }}
            placeholder="Search a medicine to explore its graph..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoFocus
          />
        </div>
        {results.length > 0 && (
          <div style={{ marginTop: "8px", border: "1px solid var(--border-color)", borderRadius: "8px", overflow: "hidden" }}>
            <table className="table" style={{ margin: 0, width: "100%" }}>
              <tbody>
                {results.map((m) => (
                  <tr key={m.id} style={{ cursor: "pointer", transition: "background 0.2s ease" }} onClick={() => { onSelect(m.id); setQuery(""); setResults([]); }} className="hover-row">
                    <td style={{ padding: "10px 16px", borderBottom: "1px solid var(--border-color)" }}>
                      <div style={{ fontWeight: 600, color: "var(--text-main)" }}>{m.particulars}</div>
                    </td>
                    <td style={{ padding: "10px 16px", color: "var(--text-muted)", textAlign: "right", borderBottom: "1px solid var(--border-color)" }}>{m.unit}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function GraphView({ medicineId, onSelectMedicine }) {
  const [graph, setGraph] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api.getMedicineGraph(medicineId)
      .then(setGraph)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [medicineId]);

  if (loading) return <p style={{ color: "var(--text-muted)", textAlign: "center", padding: "20px" }}>Loading graph...</p>;
  if (error) return <p style={{ color: "var(--danger-600)", padding: "20px" }}>{error}</p>;
  if (!graph) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <div className="card" style={{ borderLeft: "4px solid var(--primary-500)", background: "var(--bg-surface)", padding: "20px" }}>
        <h3 style={{ marginTop: 0, marginBottom: "8px", color: "var(--text-main)", fontSize: "20px" }}>{graph.particulars}</h3>
        <p style={{ color: "var(--text-secondary)", fontSize: "14px", margin: 0 }}>{graph.composition || "No composition data set"}</p>
      </div>

      <div className="graph-grid">
        <Section icon={<FlaskConical size={18} color="var(--primary-500)" />} title="Contains" count={graph.contains.length} emptyText="No composition data set for this medicine yet.">
          <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
            {graph.contains.map((c, i) => <span key={i} className="badge auto">{c.salt}</span>)}
          </div>
        </Section>

        <Section icon={<AlertTriangle size={18} color="var(--warning-500)" />} title="Interacts with" count={graph.interacts_with.length} emptyText="No known interactions flagged for these salts.">
          {graph.interacts_with.map((it, i) => {
            const meta = SEVERITY_META[it.severity] || SEVERITY_META.unknown;
            return (
              <div key={i} style={{ padding: "12px 0", borderBottom: i < graph.interacts_with.length - 1 ? "1px solid var(--border-color)" : "none" }}>
                <div className="flex-between" style={{ alignItems: "flex-start", marginBottom: "4px" }}>
                  <strong style={{ fontSize: "13px", color: "var(--text-main)", lineHeight: 1.4 }}>{it.salt} + {it.interacts_with}</strong>
                  <span style={{ background: meta.bg, color: meta.color, fontSize: "11px", padding: "2px 8px", borderRadius: "10px", fontWeight: 600, whiteSpace: "nowrap", marginLeft: "8px" }}>
                    {meta.label}
                  </span>
                </div>
                {it.note && <div style={{ fontSize: "12px", color: "var(--text-secondary)", marginTop: "4px", lineHeight: 1.4 }}>{it.note}</div>}
              </div>
            );
          })}
        </Section>

        <Section icon={<Pill size={18} color="var(--success-500)" />} title="Treats" count={graph.treats.length} emptyText="No condition mapping found for these salts.">
          <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
            {graph.treats.map((t, i) => <span key={i} className="badge learned">{t.condition}</span>)}
          </div>
        </Section>

        <Section icon={<Repeat size={18} color="var(--info-500)" />} title="Substitutes" count={graph.substitutes.length} emptyText="No substitute medicines found in the graph yet — try running a graph rebuild.">
          {graph.substitutes.map((s, i) => (
            <div
              key={s.medicine_id}
              className="graph-substitute-row"
              style={{ borderBottom: i < graph.substitutes.length - 1 ? "1px solid var(--border-color)" : "none" }}
              onClick={() => onSelectMedicine(s.medicine_id)}
            >
              <div>
                <div style={{ fontWeight: 600, fontSize: "13px", color: "var(--text-main)" }}>{s.particulars}</div>
                <div style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "2px" }}>{s.company || "—"} · Stock: {s.current_stock}</div>
              </div>
              {s.weight != null && <span className="badge auto">{s.weight}%</span>}
            </div>
          ))}
        </Section>

        <Section icon={<Building size={18} color="var(--text-main)" />} title="Supplied by" count={graph.supplied_by.length} emptyText="No confirmed bill has this medicine linked to a distributor yet.">
          <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
            {graph.supplied_by.map((d) => <span key={d.distributor_id} className="badge manual">{d.name}</span>)}
          </div>
        </Section>
      </div>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Owner-only graph rebuild trigger + status poll.
// ---------------------------------------------------------------------------
function RebuildPanel({ isOwner }) {
  const [taskId, setTaskId] = useState(null);
  const [status, setStatus] = useState(null);
  const [triggering, setTriggering] = useState(false);

  useEffect(() => {
    if (!taskId) return;
    const interval = setInterval(() => {
      api.getGraphRebuildStatus(taskId).then((s) => {
        setStatus(s);
        if (s.status !== "pending" && s.status !== "started") clearInterval(interval);
      });
    }, 2000);
    return () => clearInterval(interval);
  }, [taskId]);

  async function handleTrigger() {
    setTriggering(true);
    setStatus(null);
    try {
      const res = await api.triggerGraphRebuild();
      setTaskId(res.task_id);
    } finally {
      setTriggering(false);
    }
  }

  if (!isOwner) return null;

  return (
    <div className="card" style={{ border: "1px solid var(--border-color)", background: "var(--bg-muted)" }}>
      <div className="flex-between">
        <div>
          <h3 style={{ margin: 0, color: "var(--text-main)", display: "flex", alignItems: "center", gap: "8px" }}>
            <RefreshCw size={16} /> Graph maintenance
          </h3>
          <p style={{ color: "var(--text-secondary)", fontSize: "13px", margin: "6px 0 0", lineHeight: 1.4 }}>
            Recomputes substitute/supply edges and reloads interaction/condition data. Run this
            after a bulk composition import.
          </p>
        </div>
        <button className="btn btn-primary" onClick={handleTrigger} disabled={triggering} style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          {triggering ? <RefreshCw size={16} className="spin" /> : <RefreshCw size={16} />}
          {triggering ? "Starting..." : "Rebuild graph"}
        </button>
      </div>
      {status && (
        <div style={{ marginTop: "16px", padding: "12px", borderRadius: "8px", background: status.status === "failed" ? "var(--danger-100)" : "var(--success-100)", border: `1px solid ${status.status === "failed" ? "var(--danger-200)" : "var(--success-200)"}` }}>
          <p style={{ margin: 0, fontSize: "13px", color: status.status === "failed" ? "var(--danger-700)" : "var(--success-700)" }}>
            {status.status === "pending" && "Rebuild running in the background..."}
            {status.status === "ok" && `Done — ${JSON.stringify(status.stats)}`}
            {status.status === "failed" && `Failed: ${status.error}`}
            {!["pending", "ok", "failed"].includes(status.status) && `Status: ${status.status}...`}
          </p>
        </div>
      )}
    </div>
  );
}

export default function GraphExplorer({ isOwner = false }) {
  const [medicineId, setMedicineId] = useState(null);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.2 }}
      className="page-content"
    >
      <MedicinePicker onSelect={setMedicineId} />
      {medicineId && <GraphView medicineId={medicineId} onSelectMedicine={setMedicineId} />}
      <RebuildPanel isOwner={isOwner} />

      <style>{`
        .graph-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
          gap: 16px;
          margin-bottom: 24px;
        }
        .graph-section { margin-bottom: 0; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
        .graph-substitute-row {
          display: flex; justify-content: space-between; align-items: center;
          padding: 12px 8px; cursor: pointer; transition: background 0.2s ease;
          border-radius: 8px;
        }
        .graph-substitute-row:hover { background: var(--bg-muted); }
        .hover-row:hover { background: var(--bg-muted); }
        .spin { animation: spin 1s linear infinite; }
        @keyframes spin { 100% { transform: rotate(360deg); } }
      `}</style>
    </motion.div>
  );
}
