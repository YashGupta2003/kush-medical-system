import { useState } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { api } from "../api/client.js";

export default function SearchDashboard() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [selected, setSelected] = useState(null);
  const [history, setHistory] = useState([]);

  async function handleSearch(e) {
    const q = e.target.value;
    setQuery(q);
    if (q.length < 2) {
      setResults([]);
      return;
    }
    const data = await api.searchMedicines(q);
    setResults(data);
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
        <h2>Search medicine (Ctrl+F replacement)</h2>
        <input
          style={{ width: "100%" }}
          placeholder="Start typing a medicine name..."
          value={query}
          onChange={handleSearch}
        />
        {results.length > 0 && (
          <table style={{ marginTop: 12 }}>
            <thead>
              <tr><th>Name</th><th>Unit</th><th>MRP</th><th>Cost price</th><th>Company</th></tr>
            </thead>
            <tbody>
              {results.map((m) => (
                <tr key={m.id} onClick={() => selectMedicine(m)} style={{ cursor: "pointer" }}>
                  <td>{m.particulars}</td>
                  <td>{m.unit}</td>
                  <td>{m.mrp}</td>
                  <td>{m.net_rate}</td>
                  <td>{m.company || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
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
