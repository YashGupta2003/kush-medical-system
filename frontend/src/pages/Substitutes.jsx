import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client.js";

const MATCH_META = {
  exact: { label: "Exact composition match", badge: "auto" },
  partial: { label: "Partial match — check strength/salts before substituting", badge: "manual" },
};

function ResultsTable({ results }) {
  if (results.length === 0) return null;
  return (
    <table style={{ marginTop: 12 }}>
      <thead>
        <tr><th>Medicine</th><th>Company</th><th>Composition</th><th>MRP</th><th>In stock</th><th>Match</th></tr>
      </thead>
      <tbody>
        {results.map((r) => {
          const meta = MATCH_META[r.match_type] || { label: r.match_type, badge: "manual" };
          return (
            <tr key={r.medicine_id}>
              <td><strong>{r.particulars}</strong></td>
              <td>{r.company || "—"}</td>
              <td style={{ fontSize: 12, color: "#666" }}>{r.composition || "—"}</td>
              <td>{r.mrp != null ? `₹${r.mrp}` : "—"}</td>
              <td>{r.current_stock}</td>
              <td>
                <span className={`badge ${meta.badge}`} title={meta.label}>
                  {r.matched_salts}/{r.query_salts} salts {r.match_type === "exact" ? "✓" : ""}
                </span>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

// ---------------------------------------------------------------------------
// Mode 1: "This exact medicine is out of stock, what else works" - triggered
// automatically when arriving from SearchDashboard's "Find substitutes" button.
// ---------------------------------------------------------------------------
function ForMedicineMode({ medicineId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api.getSubstitutesForMedicine(medicineId)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [medicineId]);

  if (loading) return <p>Loading...</p>;
  if (error) return <p style={{ color: "#b91c1c" }}>{error}</p>;
  if (!data) return null;

  if (!data.medicine.composition) {
    return (
      <div className="card" style={{ borderLeft: "4px solid #ea580c" }}>
        <p style={{ margin: 0, fontSize: 13, color: "#666" }}>
          <strong>{data.medicine.particulars}</strong> doesn't have composition data saved yet.
          Add it from the Search screen (select the medicine → Composition / salt field) so
          substitutes can be found for it.
        </p>
      </div>
    );
  }

  return (
    <div className="card">
      <h3 style={{ marginTop: 0 }}>Substitutes for {data.medicine.particulars}</h3>
      <p style={{ color: "#666", fontSize: 13 }}>Composition: {data.medicine.composition}</p>
      {data.substitutes.length === 0 ? (
        <p style={{ color: "#888", fontSize: 13 }}>
          No in-stock medicine with a matching salt was found. Nothing you can substitute right now.
        </p>
      ) : (
        <ResultsTable results={data.substitutes} />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Mode 2: free-text salt search - the doctor's prescription says "Paracetamol",
// shopkeeper types it directly without needing to know a specific brand first.
// ---------------------------------------------------------------------------
function SaltSearchMode() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [searched, setSearched] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (query.trim().length < 2) { setResults([]); setSearched(false); return; }
    setLoading(true);
    setError(null);
    const t = setTimeout(() => {
      api.searchSubstitutes(query.trim())
        .then((r) => { setResults(r); setSearched(true); })
        .catch((e) => setError(e.message))
        .finally(() => setLoading(false));
    }, 300);
    return () => clearTimeout(t);
  }, [query]);

  return (
    <div className="card">
      <h3 style={{ marginTop: 0 }}>Search by salt / composition</h3>
      <p style={{ color: "#666", fontSize: 13 }}>
        Type what the prescription actually says the salt is (e.g. "Paracetamol", "Amoxicillin
        500mg") — every in-stock medicine sharing that salt will show up here, whatever brand
        it's sold under.
      </p>
      <input
        style={{ width: "100%" }}
        placeholder="e.g. Paracetamol 650mg"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      {loading && <p style={{ color: "#888", fontSize: 13, marginTop: 8 }}>Searching...</p>}
      {error && <p style={{ color: "#b91c1c", fontSize: 13, marginTop: 8 }}>{error}</p>}
      {searched && !loading && results.length === 0 && (
        <p style={{ color: "#888", fontSize: 13, marginTop: 8 }}>
          No in-stock medicine matches that salt. Double-check spelling, or this salt genuinely
          isn't in stock under any brand right now.
        </p>
      )}
      <ResultsTable results={results} />
    </div>
  );
}

export default function Substitutes() {
  const [searchParams] = useSearchParams();
  const medicineId = searchParams.get("medicine_id");

  return (
    <div>
      <div className="card">
        <h2 style={{ marginBottom: 4 }}>🔄 Substitute Finder</h2>
        <p style={{ color: "#666", fontSize: 13, marginTop: 0 }}>
          When a prescribed medicine isn't in stock, find an in-stock alternative with the same
          salt — same effect, different company. Always double-check strength/dosage before
          substituting; this only compares composition, not clinical suitability.
        </p>
      </div>

      {medicineId ? <ForMedicineMode medicineId={Number(medicineId)} /> : <SaltSearchMode />}
    </div>
  );
}
