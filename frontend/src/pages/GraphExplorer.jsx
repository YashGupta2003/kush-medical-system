import { useEffect, useState } from "react";
import { api } from "../api/client.js";

const SEVERITY_META = {
  high: { color: "#dc2626", bg: "#fee2e2", label: "High risk" },
  medium: { color: "#ca8a04", bg: "#fef3c7", label: "Medium risk" },
  low: { color: "#0284c7", bg: "#e0f2fe", label: "Low risk" },
  unknown: { color: "#666", bg: "#eee", label: "Flagged" },
};

function Section({ icon, title, count, children, emptyText }) {
  return (
    <div className="card graph-section">
      <div className="flex-between" style={{ marginBottom: 10 }}>
        <h3 style={{ margin: 0, fontSize: 15 }}>{icon} {title}</h3>
        <span style={{ fontSize: 12, color: "#888" }}>{count}</span>
      </div>
      {count === 0 ? (
        <p style={{ color: "#999", fontSize: 13, margin: 0 }}>{emptyText}</p>
      ) : children}
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
    <div className="card">
      <h2 style={{ marginBottom: 4 }}>🕸️ PharmaGraph Explorer</h2>
      <p style={{ color: "#666", fontSize: 13, marginTop: 0 }}>
        Search any medicine to see its full relationship graph — what salts it contains, what
        those salts interact with, what conditions they treat, which medicines can substitute
        for it, and which distributors have supplied it.
      </p>
      <input
        style={{ width: "100%" }}
        placeholder="Search a medicine to explore its graph..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        autoFocus
      />
      {results.length > 0 && (
        <table style={{ marginTop: 10 }}>
          <tbody>
            {results.map((m) => (
              <tr key={m.id} style={{ cursor: "pointer" }} onClick={() => { onSelect(m.id); setQuery(""); setResults([]); }}>
                <td>{m.particulars}</td>
                <td style={{ color: "#888" }}>{m.unit}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
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

  if (loading) return <p style={{ color: "#888" }}>Loading graph...</p>;
  if (error) return <p style={{ color: "#b91c1c" }}>{error}</p>;
  if (!graph) return null;

  return (
    <div className="graph-fade-in">
      <div className="card" style={{ borderLeft: "4px solid #1c1c1e" }}>
        <h3 style={{ marginTop: 0, marginBottom: 4 }}>{graph.particulars}</h3>
        <p style={{ color: "#666", fontSize: 13, margin: 0 }}>{graph.composition || "No composition data set"}</p>
      </div>

      <div className="graph-grid">
        <Section icon="🧪" title="Contains" count={graph.contains.length} emptyText="No composition data set for this medicine yet.">
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {graph.contains.map((c, i) => <span key={i} className="badge auto">{c.salt}</span>)}
          </div>
        </Section>

        <Section icon="⚠️" title="Interacts with" count={graph.interacts_with.length} emptyText="No known interactions flagged for these salts.">
          {graph.interacts_with.map((it, i) => {
            const meta = SEVERITY_META[it.severity] || SEVERITY_META.unknown;
            return (
              <div key={i} style={{ padding: "8px 0", borderBottom: i < graph.interacts_with.length - 1 ? "1px solid #f0f0f0" : "none" }}>
                <div className="flex-between">
                  <strong style={{ fontSize: 13 }}>{it.salt} + {it.interacts_with}</strong>
                  <span style={{ background: meta.bg, color: meta.color, fontSize: 11, padding: "2px 8px", borderRadius: 10, fontWeight: 600 }}>
                    {meta.label}
                  </span>
                </div>
                {it.note && <div style={{ fontSize: 12, color: "#666", marginTop: 2 }}>{it.note}</div>}
              </div>
            );
          })}
        </Section>

        <Section icon="💊" title="Treats" count={graph.treats.length} emptyText="No condition mapping found for these salts.">
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {graph.treats.map((t, i) => <span key={i} className="badge learned">{t.condition}</span>)}
          </div>
        </Section>

        <Section icon="🔄" title="Substitutes" count={graph.substitutes.length} emptyText="No substitute medicines found in the graph yet — try running a graph rebuild.">
          {graph.substitutes.map((s) => (
            <div
              key={s.medicine_id}
              className="graph-substitute-row"
              onClick={() => onSelectMedicine(s.medicine_id)}
            >
              <div>
                <div style={{ fontWeight: 600, fontSize: 13 }}>{s.particulars}</div>
                <div style={{ fontSize: 11, color: "#888" }}>{s.company || "—"} · Stock: {s.current_stock}</div>
              </div>
              {s.weight != null && <span className="badge auto">{s.weight}%</span>}
            </div>
          ))}
        </Section>

        <Section icon="🏢" title="Supplied by" count={graph.supplied_by.length} emptyText="No confirmed bill has this medicine linked to a distributor yet.">
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {graph.supplied_by.map((d) => <span key={d.distributor_id} className="badge manual">{d.name}</span>)}
          </div>
        </Section>
      </div>
    </div>
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
    <div className="card">
      <div className="flex-between">
        <div>
          <h3 style={{ margin: 0 }}>Graph maintenance</h3>
          <p style={{ color: "#666", fontSize: 13, margin: "4px 0 0" }}>
            Recomputes substitute/supply edges and reloads interaction/condition data. Run this
            after a bulk composition import.
          </p>
        </div>
        <button onClick={handleTrigger} disabled={triggering}>
          {triggering ? "Starting..." : "Rebuild graph"}
        </button>
      </div>
      {status && (
        <p style={{ fontSize: 13, marginTop: 10, color: status.status === "failed" ? "#b91c1c" : "#16a34a" }}>
          {status.status === "pending" && "Rebuild running in the background..."}
          {status.status === "ok" && `Done — ${JSON.stringify(status.stats)}`}
          {status.status === "failed" && `Failed: ${status.error}`}
        </p>
      )}
    </div>
  );
}

export default function GraphExplorer({ isOwner = false }) {
  const [medicineId, setMedicineId] = useState(null);

  return (
    <div>
      <MedicinePicker onSelect={setMedicineId} />
      {medicineId && <GraphView medicineId={medicineId} onSelectMedicine={setMedicineId} />}
      <RebuildPanel isOwner={isOwner} />

      <style>{`
        @keyframes graphFadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
        .graph-fade-in { animation: graphFadeIn 0.3s ease; }
        .graph-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
          gap: 12px;
        }
        .graph-section { margin-bottom: 0; }
        .graph-substitute-row {
          display: flex; justify-content: space-between; align-items: center;
          padding: 8px 0; border-bottom: 1px solid #f0f0f0; cursor: pointer;
        }
        .graph-substitute-row:last-child { border-bottom: none; }
        .graph-substitute-row:hover { background: #fafafa; }
      `}</style>
    </div>
  );
}
