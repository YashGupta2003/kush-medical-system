import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { CheckCircle, AlertTriangle, Package, Repeat, Search, Info } from "lucide-react";
import { api } from "../api/client.js";

const MATCH_META = {
  exact: { label: "Exact composition match", badge: "auto", icon: <CheckCircle size={14} className="mr-1 inline" /> },
  partial: { label: "Partial match — check strength/salts before substituting", badge: "manual", icon: <AlertTriangle size={14} className="mr-1 inline" /> },
};

// ---------------------------------------------------------------------------
// Small inline spinner shown while a search is in flight.
// ---------------------------------------------------------------------------
function SearchSpinner() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "10px", padding: "10px 0" }}>
      <div className="substitute-spinner" />
      <span style={{ color: "var(--text-muted)", fontSize: "13px" }}>Searching your master list...</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Animated result card - replaces the old plain table row.
// ---------------------------------------------------------------------------
function ResultCard({ result, index }) {
  const meta = MATCH_META[result.match_type] || { label: result.match_type, badge: "manual", icon: null };
  const isLowStock = result.current_stock <= 5;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(index * 0.05, 0.3), duration: 0.2 }}
      className="substitute-result-card"
    >
      <div className="flex-between" style={{ alignItems: "flex-start" }}>
        <div>
          <div style={{ fontSize: "15px", fontWeight: 700, color: "var(--text-main)" }}>{result.particulars}</div>
          <div style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "2px" }}>{result.company || "Company not set"}</div>
        </div>
        <span className={`badge ${meta.badge}`} title={meta.label} style={{ display: "flex", alignItems: "center" }}>
          {meta.icon} {result.matched_salts}/{result.query_salts} salts
        </span>
      </div>

      <div style={{ fontSize: "12px", color: "var(--text-secondary)", marginTop: "8px", lineHeight: 1.5 }}>
        {result.composition || "—"}
      </div>

      <div className="item-card-footer" style={{ marginTop: "12px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span className="cost-pill" style={isLowStock ? { background: "var(--warning-100)", color: "var(--warning-700)" } : { background: "var(--bg-muted)", color: "var(--text-secondary)", padding: "4px 8px", borderRadius: "12px", fontSize: "12px", display: "flex", alignItems: "center", gap: "4px" }}>
          <Package size={14} /> {result.current_stock} in stock
        </span>
        <span style={{ fontSize: "13px", fontWeight: 600, color: "var(--text-main)" }}>
          {result.mrp != null ? `₹${result.mrp}` : "MRP not set"}
        </span>
      </div>
    </motion.div>
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
// Smarter empty-state
// ---------------------------------------------------------------------------
function EmptyState({ query, availability, checkingAvailability }) {
  if (checkingAvailability) {
    return <p style={{ color: "var(--text-muted)", fontSize: "13px", marginTop: "8px" }}>Checking your full catalog...</p>;
  }
  if (!availability) return null;

  if (!availability.exists_in_catalog) {
    return (
      <div className="card" style={{ borderLeft: "4px solid var(--danger-500)", marginTop: "12px", display: "flex", gap: "10px", alignItems: "flex-start" }}>
        <Info size={18} color="var(--danger-500)" style={{ flexShrink: 0, marginTop: "2px" }} />
        <p style={{ margin: 0, fontSize: "13px", color: "var(--text-secondary)", lineHeight: 1.5 }}>
          <strong>"{query}"</strong> doesn't match any salt in your master list yet — either the
          spelling doesn't match how it's stored, or composition data hasn't been filled in for
          any medicine with this salt. Try a shorter/simpler spelling, or add composition data
          from the Search screen.
        </p>
      </div>
    );
  }

  return (
    <div className="card" style={{ borderLeft: "4px solid var(--warning-500)", marginTop: "12px", display: "flex", gap: "10px", alignItems: "flex-start" }}>
      <Info size={18} color="var(--warning-500)" style={{ flexShrink: 0, marginTop: "2px" }} />
      <p style={{ margin: 0, fontSize: "13px", color: "var(--text-secondary)", lineHeight: 1.5 }}>
        <strong>{availability.out_of_stock_count}</strong> medicine{availability.out_of_stock_count === 1 ? "" : "s"} in
        your master list {availability.out_of_stock_count === 1 ? "has" : "have"} this salt, but none currently
        have stock. Turn on <strong>"Include out-of-stock"</strong> below to see them anyway — useful for
        deciding what to reorder.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Mode 1: "This exact medicine is out of stock, what else works"
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
  if (error) return <p style={{ color: "var(--danger-600)" }}>{error}</p>;
  if (!data) return null;

  if (!data.medicine.composition) {
    return (
      <div className="card" style={{ borderLeft: "4px solid var(--warning-500)", display: "flex", gap: "10px", alignItems: "flex-start" }}>
        <Info size={18} color="var(--warning-500)" style={{ flexShrink: 0, marginTop: "2px" }} />
        <p style={{ margin: 0, fontSize: "13px", color: "var(--text-secondary)", lineHeight: 1.5 }}>
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
          <h3 style={{ marginTop: 0, marginBottom: "4px", color: "var(--text-main)" }}>Substitutes for {data.medicine.particulars}</h3>
          <p style={{ color: "var(--text-muted)", fontSize: "13px", margin: 0 }}>Composition: {data.medicine.composition}</p>
        </div>
        <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "13px", color: "var(--text-secondary)", whiteSpace: "nowrap", cursor: "pointer" }}>
          <input type="checkbox" checked={includeOutOfStock} onChange={(e) => setIncludeOutOfStock(e.target.checked)} />
          Include out-of-stock
        </label>
      </div>

      {data.substitutes.length === 0 ? (
        <p style={{ color: "var(--text-muted)", fontSize: "13px", marginTop: "12px" }}>
          No {includeOutOfStock ? "" : "in-stock "}medicine with a matching salt was found.
        </p>
      ) : (
        <div style={{ marginTop: "16px" }}>
          <ResultsGrid results={data.substitutes} />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Mode 2: free-text salt search
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
      <h3 style={{ marginTop: 0, color: "var(--text-main)" }}>Search by salt / composition</h3>
      <p style={{ color: "var(--text-secondary)", fontSize: "13px", marginBottom: "16px", lineHeight: 1.5 }}>
        Type what the prescription actually says the salt is (e.g. "Paracetamol", "Amoxicillin
        500mg") — even a partial name works. Every medicine sharing that salt shows up here,
        whatever brand it's sold under.
      </p>

      <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
        <div style={{ position: "relative", flex: 1 }}>
          <Search size={16} style={{ position: "absolute", left: "12px", top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }} />
          <input
            style={{ width: "100%", paddingLeft: "36px" }}
            placeholder="e.g. Paracetamol"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoFocus
          />
        </div>
        <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "13px", color: "var(--text-secondary)", whiteSpace: "nowrap", cursor: "pointer" }}>
          <input type="checkbox" checked={includeOutOfStock} onChange={(e) => setIncludeOutOfStock(e.target.checked)} />
          Include out-of-stock
        </label>
      </div>

      {loading && <SearchSpinner />}
      {error && <p style={{ color: "var(--danger-600)", fontSize: "13px", marginTop: "8px" }}>{error}</p>}

      {searched && !loading && results.length === 0 && (
        <EmptyState query={query} availability={availability} checkingAvailability={checkingAvailability} />
      )}

      {!loading && results.length > 0 && (
        <div style={{ marginTop: "16px" }}>
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
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.2 }}
      className="page-content"
    >
      <div className="card" style={{ display: "flex", gap: "12px", alignItems: "flex-start" }}>
        <div style={{ background: "var(--primary-100)", padding: "10px", borderRadius: "10px" }}>
          <Repeat size={24} color="var(--primary-600)" />
        </div>
        <div>
          <h2 style={{ margin: "0 0 4px 0", color: "var(--text-main)" }}>Substitute Finder</h2>
          <p style={{ color: "var(--text-secondary)", fontSize: "13px", margin: 0, lineHeight: 1.5 }}>
            When a prescribed medicine isn't in stock, find an in-stock alternative with the same
            salt — same effect, different company. Always double-check strength/dosage before
            substituting; this only compares composition, not clinical suitability.
          </p>
        </div>
      </div>

      {medicineId ? <ForMedicineMode medicineId={Number(medicineId)} /> : <SaltSearchMode />}

      <style>{`
        .substitute-results-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
          gap: 16px;
        }
        .substitute-result-card {
          border: 1px solid var(--border-color);
          border-radius: 12px;
          padding: 16px;
          background: var(--bg-surface);
          transition: box-shadow 0.2s ease, border-color 0.2s ease;
        }
        .substitute-result-card:hover {
          box-shadow: 0 4px 14px rgba(0,0,0,0.05);
          border-color: var(--primary-300);
        }
        .substitute-spinner {
          width: 16px; height: 16px;
          border: 2px solid var(--border-color);
          border-top-color: var(--primary-500);
          border-radius: 50%;
          animation: substituteSpin 0.7s linear infinite;
        }
        @keyframes substituteSpin { to { transform: rotate(360deg); } }
      `}</style>
    </motion.div>
  );
}
