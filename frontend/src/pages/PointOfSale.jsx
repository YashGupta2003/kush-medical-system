import { useEffect, useState } from "react";
import { api } from "../api/client.js";

const SEVERITY_META = {
  high: { color: "#dc2626", bg: "#fee2e2", border: "#fecaca", label: "High risk", icon: "🚫" },
  medium: { color: "#ca8a04", bg: "#fef3c7", border: "#fde68a", label: "Medium risk", icon: "⚠️" },
  low: { color: "#0284c7", bg: "#e0f2fe", border: "#bae6fd", label: "Low risk", icon: "ℹ️" },
  unknown: { color: "#666", bg: "#eee", border: "#ddd", label: "Flagged", icon: "⚠️" },
};

// ---------------------------------------------------------------------------
// Add-to-cart medicine search
// ---------------------------------------------------------------------------
function MedicineSearch({ onAdd, excludeIds }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);

  useEffect(() => {
    if (query.trim().length < 2) { setResults([]); return; }
    const t = setTimeout(() => {
      api.browseMedicines({ q: query, page: 1, page_size: 8 }).then((d) =>
        setResults(d.items.filter((m) => !excludeIds.includes(m.id)))
      );
    }, 250);
    return () => clearTimeout(t);
  }, [query, excludeIds]);

  return (
    <div>
      <input
        style={{ width: "100%" }}
        placeholder="Search medicine to add to cart..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      {results.length > 0 && (
        <table style={{ marginTop: 8 }}>
          <tbody>
            {results.map((m) => (
              <tr key={m.id} style={{ cursor: "pointer" }} onClick={() => { onAdd(m); setQuery(""); setResults([]); }}>
                <td>{m.particulars}</td>
                <td style={{ color: "#888" }}>{m.unit}</td>
                <td style={{ color: m.current_stock > 0 ? "#16a34a" : "#dc2626" }}>
                  {m.current_stock > 0 ? `${m.current_stock} in stock` : "Out of stock"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Interaction warning banner
// ---------------------------------------------------------------------------
function InteractionWarning({ interactions, onAcknowledge, acknowledging }) {
  if (!interactions || interactions.length === 0) return null;
  const worst = interactions.reduce((acc, i) => {
    const order = { high: 3, medium: 2, low: 1, unknown: 0 };
    return (order[i.severity] || 0) > (order[acc] || 0) ? i.severity : acc;
  }, "unknown");
  const meta = SEVERITY_META[worst] || SEVERITY_META.unknown;

  return (
    <div className="pos-warning-banner" style={{ background: meta.bg, borderColor: meta.border }}>
      <div className="pos-warning-header">
        <span className="pos-warning-icon">{meta.icon}</span>
        <strong style={{ color: meta.color }}>Possible drug interaction in this cart</strong>
      </div>
      {interactions.map((i, idx) => {
        const m = SEVERITY_META[i.severity] || SEVERITY_META.unknown;
        return (
          <div key={idx} className="pos-warning-row">
            <span className="pos-warning-pair">{i.salt_a} + {i.salt_b}</span>
            <span className="pos-warning-severity" style={{ color: m.color }}>{m.label}</span>
            {i.note && <div className="pos-warning-note">{i.note}</div>}
          </div>
        );
      })}
      <p className="pos-warning-disclaimer">
        This only flags a known composition-level interaction — it is not a diagnosis or dosing
        instruction. Use your own pharmacist judgment; if you're confident this combination is
        appropriate for this customer, confirm below to proceed.
      </p>
      {onAcknowledge && (
        <button className="pos-override-btn" onClick={onAcknowledge} disabled={acknowledging}>
          {acknowledging ? "Confirming..." : "I understand — record this sale anyway"}
        </button>
      )}
    </div>
  );
}

export default function PointOfSale() {
  const [cart, setCart] = useState([]);           // [{medicine, qty}]
  const [checking, setChecking] = useState(false);
  const [checkResult, setCheckResult] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  // Live-check the cart every time it changes (debounced), so the
  // pharmacist sees the warning WHILE building the cart, not just at
  // checkout.
  useEffect(() => {
    setCheckResult(null);
    setSuccess(null);
    if (cart.length < 2) return;
    setChecking(true);
    const t = setTimeout(() => {
      api.checkCart(cart.map((c) => ({ medicine_id: c.medicine.id, qty_sold: c.qty })))
        .then(setCheckResult)
        .catch((e) => setError(e.message))
        .finally(() => setChecking(false));
    }, 350);
    return () => clearTimeout(t);
  }, [cart]);

  function addToCart(medicine) {
    setCart((prev) => [...prev, { medicine, qty: 1 }]);
  }

  function updateQty(medicineId, qty) {
    setCart((prev) => prev.map((c) => (c.medicine.id === medicineId ? { ...c, qty: Number(qty) || 0 } : c)));
  }

  function removeFromCart(medicineId) {
    setCart((prev) => prev.filter((c) => c.medicine.id !== medicineId));
  }

  async function submitCart(confirmOverride = false) {
    setError(null);
    setSubmitting(true);
    try {
      const res = await api.recordCartSale(
        cart.map((c) => ({ medicine_id: c.medicine.id, qty_sold: c.qty })),
        confirmOverride,
      );
      if (res.status === "needs_confirmation") {
        setCheckResult(res);
      } else {
        setSuccess(`Sale recorded — ${cart.length} item${cart.length === 1 ? "" : "s"} sold.`);
        setCart([]);
        setCheckResult(null);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  const cartIds = cart.map((c) => c.medicine.id);
  const hasBlockingWarning = checkResult && checkResult.has_interactions;

  return (
    <div>
      <div className="card">
        <h2 style={{ marginBottom: 4 }}>🛒 Point of Sale</h2>
        <p style={{ color: "#666", fontSize: 13, marginTop: 0 }}>
          Add every medicine a customer is buying in this visit to the cart — as soon as there are
          2 or more items, they're automatically checked against each other for known drug
          interactions before the sale is recorded.
        </p>
        <MedicineSearch onAdd={addToCart} excludeIds={cartIds} />
      </div>

      {cart.length > 0 && (
        <div className="card pos-fade-in">
          <h3 style={{ marginTop: 0 }}>Cart ({cart.length})</h3>
          {cart.map((c) => (
            <div key={c.medicine.id} className="pos-cart-row">
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: 14 }}>{c.medicine.particulars}</div>
                <div style={{ fontSize: 12, color: "#888" }}>{c.medicine.composition || "No composition data"}</div>
              </div>
              <input
                type="number" min="0.01" step="0.01" style={{ width: 70 }}
                value={c.qty} onChange={(e) => updateQty(c.medicine.id, e.target.value)}
              />
              <button className="secondary" onClick={() => removeFromCart(c.medicine.id)}>Remove</button>
            </div>
          ))}

          {checking && <p className="pos-checking-text">🔎 Checking for interactions...</p>}

          <InteractionWarning
            interactions={checkResult?.interactions}
            onAcknowledge={() => submitCart(true)}
            acknowledging={submitting}
          />

          {error && <p style={{ color: "#b91c1c", fontSize: 13, marginTop: 10 }}>{error}</p>}

          {!hasBlockingWarning && (
            <button
              style={{ marginTop: 14 }}
              onClick={() => submitCart(false)}
              disabled={submitting || checking || cart.some((c) => !c.qty || c.qty <= 0)}
            >
              {submitting ? "Recording..." : `Complete sale (${cart.length} item${cart.length === 1 ? "" : "s"})`}
            </button>
          )}
        </div>
      )}

      {success && (
        <div className="card pos-success-card pos-fade-in">
          <span className="pos-success-check">✓</span> {success}
        </div>
      )}

      <style>{`
        @keyframes posFadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
        .pos-fade-in { animation: posFadeIn 0.3s ease; }

        .pos-cart-row {
          display: flex; align-items: center; gap: 10px; padding: 10px 0;
          border-bottom: 1px solid #f0f0f0;
        }
        .pos-cart-row:last-of-type { border-bottom: none; }

        .pos-checking-text { color: #888; font-size: 13px; margin: 10px 0 0; }

        .pos-warning-banner {
          border: 1px solid; border-radius: 12px; padding: 14px 16px; margin-top: 14px;
          animation: posFadeIn 0.25s ease;
        }
        .pos-warning-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; font-size: 14px; }
        .pos-warning-icon { font-size: 16px; }
        .pos-warning-row { padding: 6px 0; border-top: 1px solid rgba(0,0,0,0.06); }
        .pos-warning-pair { font-weight: 600; font-size: 13px; }
        .pos-warning-severity { font-size: 11px; font-weight: 700; margin-left: 8px; text-transform: uppercase; }
        .pos-warning-note { font-size: 12.5px; color: #555; margin-top: 3px; }
        .pos-warning-disclaimer { font-size: 12px; color: #666; margin: 10px 0 0; line-height: 1.5; }
        .pos-override-btn {
          margin-top: 10px; background: #fff; border: 1px solid #999; color: #333;
        }

        .pos-success-card {
          display: flex; align-items: center; gap: 10px; border-left: 4px solid #16a34a;
          color: #14532d; font-weight: 600;
        }
        .pos-success-check {
          width: 26px; height: 26px; border-radius: 50%; background: #16a34a; color: #fff;
          display: flex; align-items: center; justify-content: center; font-size: 14px; flex-shrink: 0;
        }
      `}</style>
    </div>
  );
}