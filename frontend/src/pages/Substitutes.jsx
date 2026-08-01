import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client.js";

const MATCH_META = {
  exact: { label: "Exact composition match", badge: "auto", icon: "✅" },
  partial: { label: "Partial match — check strength/salts before substituting", badge: "manual", icon: "⚠️" },
};

// ---------------------------------------------------------------------------
// Small inline spinner shown while a search is in flight.
// ---------------------------------------------------------------------------
function SearchSpinner() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 0" }}>
      <div className="substitute-spinner" />
      <span style={{ color: "#888", fontSize: 13 }}>Searching your master list...</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Animated result card - replaces the old plain table row.
// ---------------------------------------------------------------------------
function ResultCard({ result, index }) {
  const meta = MATCH_META[result.match_type] || { label: result.match_type, badge: "manual", icon: "" };
  const isLowStock = result.current_stock <= 5;

  return (
    <div
      className="substitute-result-card"
      style={{ animationDelay: `${Math.min(index * 60, 480)}ms` }}
    >
      <div className="flex-between" style={{ alignItems: "flex-start" }}>
        <div>
          <div style={{ fontSize: 15, fontWeight: 700 }}>{result.particulars}</div>
          <div style={{ fontSize: 12, color: "#888", marginTop: 2 }}>{result.company || "Company not set"}</div>
        </div>
        <span className={`badge ${meta.badge}`} title={meta.label}>
          {meta.icon} {result.matched_salts}/{result.query_salts} salts
        </span>
      </div>

      <div style={{ fontSize: 12, color: "#555", marginTop: 8, lineHeight: 1.5 }}>
        {result.composition || "—"}
      </div>

      <div className="item-card-footer" style={{ marginTop: 10 }}>
        <span className="cost-pill" style={isLowStock ? { background: "#fef3c7", color: "#78350f" } : undefined}>
          📦 {result.current_stock} in stock
        </span>
        <span style={{ fontSize: 13, fontWeight: 600 }}>
          {result.mrp != null ? `₹${result.mrp}` : "MRP not set"}
        </span>
      </div>
    </div>
  );
}

function ResultsGrid({ results }) {
  if (results.length === 0) return null;
  return (
    <div className="substitute-results-grid">
      {results.map((r, i) => <ResultCard key={r.medicine_id} result={r} index={i} />)}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Smarter empty-state: tells the shopkeeper WHY nothing showed up, instead
// of one generic message for every case.
// ---------------------------------------------------------------------------
function EmptyState({ query, availability, checkingAvailability }) {
  if (checkingAvailability) {
    return <p style={{ color: "#888", fontSize: 13, marginTop: 8 }}>Checking your full catalog...</p>;
  }
  if (!availability) return null;

  if (!availability.exists_in_catalog) {
    return (
      <div className="card" style={{ borderLeft: "4px solid #dc2626", marginTop: 12 }}>
        <p style={{ margin: 0, fontSize: 13, color: "#666" }}>
          <strong>"{query}"</strong> doesn't match any salt in your master list yet — either the
          spelling doesn't match how it's stored, or composition data hasn't been filled in for
          any medicine with this salt. Try a shorter/simpler spelling, or add composition data
          from the Search screen.
        </p>
      </div>
    );
  }

  return (
    <div className="card" style={{ borderLeft: "4px solid #ea580c", marginTop: 12 }}>
      <p style={{ margin: 0, fontSize: 13, color: "#666" }}>
        <strong>{availability.out_of_stock_count}</strong> medicine{availability.out_of_stock_count === 1 ? "" : "s"} in
        your master list {availability.out_of_stock_count === 1 ? "has" : "have"} this salt, but none currently
        have stock. Turn on <strong>"Include out-of-stock"</strong> below to see them anyway — useful for
        deciding what to reorder.
      </p>
    </div>
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
  const [includeOutOfStock, setIncludeOutOfStock] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api.getSubstitutesForMedicine(medicineId, !includeOutOfStock)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [medicineId, includeOutOfStock]);

  if (loading) return <SearchSpinner />;
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
    <div className="card substitute-fade-in">
      <div className="flex-between">
        <div>
          <h3 style={{ marginTop: 0, marginBottom: 4 }}>Substitutes for {data.medicine.particulars}</h3>
          <p style={{ color: "#666", fontSize: 13, margin: 0 }}>Composition: {data.medicine.composition}</p>
        </div>
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "#444", whiteSpace: "nowrap" }}>
          <input type="checkbox" checked={includeOutOfStock} onChange={(e) => setIncludeOutOfStock(e.target.checked)} />
          Include out-of-stock
        </label>
      </div>

      {data.substitutes.length === 0 ? (
        <p style={{ color: "#888", fontSize: 13, marginTop: 10 }}>
          No {includeOutOfStock ? "" : "in-stock "}medicine with a matching salt was found.
        </p>
      ) : (
        <div style={{ marginTop: 12 }}>
          <ResultsGrid results={data.substitutes} />
        </div>
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
  const [includeOutOfStock, setIncludeOutOfStock] = useState(false);
  const [results, setResults] = useState([]);
  const [searched, setSearched] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [availability, setAvailability] = useState(null);
  const [checkingAvailability, setCheckingAvailability] = useState(false);

  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([]);
      setSearched(false);
      setAvailability(null);
      return;
    }
    setLoading(true);
    setError(null);
    setAvailability(null);
    const t = setTimeout(() => {
      api.searchSubstitutes(query.trim(), !includeOutOfStock)
        .then((r) => {
          setResults(r);
          setSearched(true);
          if (r.length === 0) {
            setCheckingAvailability(true);
            api.checkSaltAvailability(query.trim())
              .then(setAvailability)
              .finally(() => setCheckingAvailability(false));
          }
        })
        .catch((e) => setError(e.message))
        .finally(() => setLoading(false));
    }, 300);
    return () => clearTimeout(t);
  }, [query, includeOutOfStock]);

  return (
    <div className="card">
      <h3 style={{ marginTop: 0 }}>Search by salt / composition</h3>
      <p style={{ color: "#666", fontSize: 13 }}>
        Type what the prescription actually says the salt is (e.g. "Paracetamol", "Amoxicillin
        500mg") — even a partial name works. Every medicine sharing that salt shows up here,
        whatever brand it's sold under.
      </p>

      <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
        <input
          style={{ flex: 1 }}
          placeholder="e.g. Paracetamol"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          autoFocus
        />
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "#444", whiteSpace: "nowrap" }}>
          <input type="checkbox" checked={includeOutOfStock} onChange={(e) => setIncludeOutOfStock(e.target.checked)} />
          Include out-of-stock
        </label>
      </div>

      {loading && <SearchSpinner />}
      {error && <p style={{ color: "#b91c1c", fontSize: 13, marginTop: 8 }}>{error}</p>}

      {searched && !loading && results.length === 0 && (
        <EmptyState query={query} availability={availability} checkingAvailability={checkingAvailability} />
      )}

      {!loading && results.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <ResultsGrid results={results} />
        </div>
      )}
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

      <style>{`
        @keyframes substituteFadeInUp {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .substitute-fade-in { animation: substituteFadeInUp 0.3s ease; }
        .substitute-results-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
          gap: 12px;
        }
        .substitute-result-card {
          border: 1px solid #e5e5e5;
          border-radius: 12px;
          padding: 14px;
          background: #fff;
          opacity: 0;
          animation: substituteFadeInUp 0.35s ease forwards;
          transition: box-shadow 0.15s ease, transform 0.15s ease;
        }
        .substitute-result-card:hover {
          box-shadow: 0 4px 14px rgba(0,0,0,0.08);
          transform: translateY(-2px);
        }
        .substitute-spinner {
          width: 16px; height: 16px;
          border: 2px solid #e5e5e5;
          border-top-color: #1c1c1e;
          border-radius: 50%;
          animation: substituteSpin 0.7s linear infinite;
        }
        @keyframes substituteSpin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
