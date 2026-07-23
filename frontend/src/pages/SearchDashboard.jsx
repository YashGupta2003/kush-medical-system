import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { api } from "../api/client.js";

const PAGE_SIZE = 50;

export default function SearchDashboard() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(null);
  const [history, setHistory] = useState([]);

  // Load the full list (or a filtered page of it) whenever the query or page changes.
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
    setPage(1); // reset to the first page whenever the search text changes
  }

  async function selectMedicine(med) {
    setSelected(med);
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
  }

  return (
    <div>
      <div className="card">
        <h2>Medicine list</h2>
        <p style={{ color: "#666", fontSize: 13 }}>
          Your full rate list is shown below. Start typing to narrow it down (Ctrl+F replacement).
        </p>
        <input
          style={{ width: "100%" }}
          placeholder="Start typing a medicine name to filter, or just scroll to browse everything..."
          value={query}
          onChange={handleSearchChange}
        />
        <p style={{ color: "#999", fontSize: 12, marginTop: 6 }}>
          Showing {results.length} of {total} medicines{query ? ` matching "${query}"` : ""}
        </p>

       <table style={{ marginTop: 12 }}>
            <thead>
              <tr><th>Name</th><th>Unit</th><th>MRP</th><th>Cost price</th><th>Stock</th><th>Company</th></tr>
            </thead>
            <tbody>
              {results.map((m) => {
                const isLow = m.low_stock_threshold != null && m.current_stock != null && m.current_stock < m.low_stock_threshold;
                return (
                  <tr key={m.id} onClick={() => selectMedicine(m)} style={{ cursor: "pointer" }}>
                    <td>{m.particulars}</td>
                    <td>{m.unit}</td>
                    <td>{m.mrp}</td>
                    <td>{m.net_rate}</td>
                    <td>{isLow ? <span className="badge unmatched">{m.current_stock} low!</span> : (m.current_stock ?? "—")}</td>
                    <td>{m.company || "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>

        {results.length < total && (
          <button
            className="secondary"
            style={{ marginTop: 10 }}
            disabled={loading}
            onClick={() => setPage((p) => p + 1)}
          >
            {loading ? "Loading..." : `Load more (${total - results.length} remaining)`}
          </button>
        )}
      </div>

      {selected && (
        <div className="card">
          <h3>{selected.particulars}</h3>
          <p>Current MRP: <strong>{selected.mrp}</strong> · Current cost price: <strong>{selected.net_rate}</strong></p>
          {history.length > 1 ? (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={history}>
                <XAxis dataKey="date" fontSize={11} />
                <YAxis fontSize={11} />
                <Tooltip />
                <Line type="monotone" dataKey="net_rate" stroke="#1c1c1e" strokeWidth={2} dot />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <p style={{ color: "#666", fontSize: 13 }}>
              Not enough price history yet — this builds up as bills are confirmed over time.
            </p>
          )}
        </div>
      )}
    </div>
  );
}