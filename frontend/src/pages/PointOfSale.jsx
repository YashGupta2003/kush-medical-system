import { useEffect, useRef, useState } from "react";
import { api } from "../api/client.js";

const SEVERITY_META = {
  high: { color: "#dc2626", bg: "#fee2e2", border: "#fecaca", label: "High risk", icon: "🚫" },
  medium: { color: "#ca8a04", bg: "#fef3c7", border: "#fde68a", label: "Medium risk", icon: "⚠️" },
  low: { color: "#0284c7", bg: "#e0f2fe", border: "#bae6fd", label: "Low risk", icon: "ℹ️" },
  unknown: { color: "#666", bg: "#eee", border: "#ddd", label: "Flagged", icon: "⚠️" },
};

function formatMoney(n) {
  if (n == null) return "—";
  return "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

// ---------------------------------------------------------------------------
// Add-to-cart medicine search
// ---------------------------------------------------------------------------
function MedicineSearch({ onAdd, excludeIds }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    if (query.trim().length < 2) { setResults([]); setSearching(false); return; }
    setSearching(true);
    const t = setTimeout(() => {
      api.browseMedicines({ q: query, page: 1, page_size: 8 }).then((d) =>
        setResults(d.items.filter((m) => !excludeIds.includes(m.id)))
      ).finally(() => setSearching(false));
    }, 250);
    return () => clearTimeout(t);
  }, [query, excludeIds]);

  return (
    <div className="pos-search-wrap">
      <div className="pos-search-input-wrap">
        <span className="pos-search-icon">🔍</span>
        <input
          className="pos-search-input"
          placeholder="Search medicine to add to cart..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        {searching && <span className="pos-search-spinner" />}
      </div>
      {results.length > 0 && (
        <div className="pos-search-results">
          {results.map((m, i) => (
            <div
              key={m.id}
              className="pos-search-result-row"
              style={{ animationDelay: `${Math.min(i * 30, 200)}ms` }}
              onClick={() => { onAdd(m); setQuery(""); setResults([]); }}
            >
              <div className="pos-search-result-main">
                <div className="pos-search-result-name">{m.particulars}</div>
                <div className="pos-search-result-meta">
                  {m.unit || "—"} {m.mrp != null && <>· {formatMoney(m.mrp)}</>}
                </div>
              </div>
              <span className={`pos-stock-pill ${m.current_stock > 0 ? "in" : "out"}`}>
                {m.current_stock > 0 ? `${m.current_stock} in stock` : "Out of stock"}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Quantity stepper — nicer than a bare number input for a POS screen where
// staff are adjusting quantities quickly between customers.
// ---------------------------------------------------------------------------
function QtyStepper({ qty, onChange }) {
  const step = 1;
  function bump(delta) {
    const next = Math.max(0, Math.round((Number(qty || 0) + delta) * 100) / 100);
    onChange(next);
  }
  return (
    <div className="pos-qty-stepper">
      <button type="button" className="pos-qty-btn" onClick={() => bump(-step)}>−</button>
      <input
        type="number" min="0" step="0.01"
        value={qty}
        onChange={(e) => onChange(Number(e.target.value) || 0)}
      />
      <button type="button" className="pos-qty-btn" onClick={() => bump(step)}>+</button>
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

// ---------------------------------------------------------------------------
// Empty-cart placeholder
// ---------------------------------------------------------------------------
function EmptyCartState() {
  return (
    <div className="pos-empty-state">
      <div className="pos-empty-icon">🧾</div>
      <div className="pos-empty-title">Cart is empty</div>
      <div className="pos-empty-sub">Search for a medicine above to start building this sale.</div>
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
  const topRef = useRef(null);

  // Live-check the cart every time it changes (debounced), so the
  // pharmacist sees the warning WHILE building the cart, not just at
  // checkout.
  useEffect(() => {
    setCheckResult(null);
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
    setSuccess(null);
    setCart((prev) => [...prev, { medicine, qty: 1 }]);
  }

  function updateQty(medicineId, qty) {
    setCart((prev) => prev.map((c) => (c.medicine.id === medicineId ? { ...c, qty } : c)));
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
        // Scroll the confirmation into view - without this, a success that
        // happens while scrolled down the cart list can feel like nothing
        // happened at all.
        topRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  const cartIds = cart.map((c) => c.medicine.id);
  const hasBlockingWarning = checkResult && checkResult.has_interactions;
  const cartTotal = cart.reduce((sum, c) => sum + (c.medicine.mrp != null ? c.medicine.mrp * (c.qty || 0) : 0), 0);
  const totalUnits = cart.reduce((sum, c) => sum + (Number(c.qty) || 0), 0);
  const canSubmit = !submitting && !checking && cart.length > 0 && cart.every((c) => c.qty > 0);

  return (
    <div>
      <div ref={topRef} />

      {success && (
        <div className="card pos-success-card pos-fade-in">
          <span className="pos-success-check">✓</span>
          <div>
            <div>{success}</div>
            <div className="pos-success-sub">Stock levels and the sales ledger have been updated.</div>
          </div>
          <button className="secondary pos-success-dismiss" onClick={() => setSuccess(null)}>Dismiss</button>
        </div>
      )}

      <div className="card pos-header-card">
        <h2 style={{ marginBottom: 4 }}>🛒 Point of Sale</h2>
        <p style={{ color: "#666", fontSize: 13, marginTop: 0 }}>
          Add every medicine a customer is buying in this visit to the cart — as soon as there are
          2 or more items, they're automatically checked against each other for known drug
          interactions and duplicate active ingredients before the sale is recorded.
        </p>
        <MedicineSearch onAdd={addToCart} excludeIds={cartIds} />
      </div>

      <div className="card pos-cart-card">
        <div className="flex-between" style={{ marginBottom: cart.length ? 10 : 0 }}>
          <h3 style={{ margin: 0 }}>Cart {cart.length > 0 && `(${cart.length})`}</h3>
          {cart.length > 0 && (
            <span className="pos-cart-total-pill">
              {totalUnits} unit{totalUnits === 1 ? "" : "s"} · {formatMoney(cartTotal)}
            </span>
          )}
        </div>

        {cart.length === 0 && <EmptyCartState />}

        {cart.map((c) => (
          <div key={c.medicine.id} className="pos-cart-row pos-fade-in">
            <div className="pos-cart-row-main">
              <div className="pos-cart-row-name">{c.medicine.particulars}</div>
              <div className="pos-cart-row-meta">
                {c.medicine.composition || "No composition data"}
                {c.medicine.mrp != null && <span className="pos-cart-row-mrp"> · {formatMoney(c.medicine.mrp)} each</span>}
              </div>
            </div>
            <QtyStepper qty={c.qty} onChange={(v) => updateQty(c.medicine.id, v)} />
            <button className="secondary pos-remove-btn" onClick={() => removeFromCart(c.medicine.id)} title="Remove item">
              ✕
            </button>
          </div>
        ))}

        {checking && (
          <p className="pos-checking-text">
            <span className="pos-checking-spinner" /> Checking for interactions...
          </p>
        )}

        <InteractionWarning
          interactions={checkResult?.interactions}
          onAcknowledge={() => submitCart(true)}
          acknowledging={submitting}
        />

        {error && <p style={{ color: "#b91c1c", fontSize: 13, marginTop: 10 }}>{error}</p>}

        {cart.length > 0 && !hasBlockingWarning && (
          <div className="pos-checkout-row">
            <div className="pos-checkout-summary">
              <span className="pos-checkout-label">Total</span>
              <span className="pos-checkout-value">{formatMoney(cartTotal)}</span>
            </div>
            <button
              className="pos-complete-btn"
              onClick={() => submitCart(false)}
              disabled={!canSubmit}
            >
              {submitting ? "Recording..." : `Complete sale (${cart.length} item${cart.length === 1 ? "" : "s"})`}
            </button>
          </div>
        )}
      </div>

      <style>{`
        @keyframes posFadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes posFadeInRow { from { opacity: 0; transform: translateX(-6px); } to { opacity: 1; transform: translateX(0); } }
        .pos-fade-in { animation: posFadeIn 0.3s ease; }

        .pos-header-card { background: linear-gradient(135deg, #fff, #fafbff); }

        /* --- search --- */
        .pos-search-wrap { position: relative; }
        .pos-search-input-wrap {
          position: relative; display: flex; align-items: center;
        }
        .pos-search-icon { position: absolute; left: 12px; font-size: 14px; opacity: 0.5; pointer-events: none; }
        .pos-search-input {
          width: 100%; padding-left: 34px !important; padding-top: 10px; padding-bottom: 10px;
          border: 1.5px solid #e2e2e5; transition: border-color 0.15s ease, box-shadow 0.15s ease;
        }
        .pos-search-input:focus {
          outline: none; border-color: #1c1c1e; box-shadow: 0 0 0 3px rgba(28,28,30,0.08);
        }
        .pos-search-spinner {
          position: absolute; right: 12px; width: 14px; height: 14px;
          border: 2px solid #e5e5e5; border-top-color: #1c1c1e; border-radius: 50%;
          animation: posSpin 0.7s linear infinite;
        }
        .pos-search-results {
          margin-top: 8px; border: 1px solid #eee; border-radius: 10px; overflow: hidden;
          box-shadow: 0 4px 16px rgba(0,0,0,0.06);
        }
        .pos-search-result-row {
          display: flex; justify-content: space-between; align-items: center;
          padding: 10px 14px; cursor: pointer; border-bottom: 1px solid #f2f2f2;
          background: #fff; opacity: 0; animation: posFadeInRow 0.25s ease forwards;
          transition: background 0.12s ease;
        }
        .pos-search-result-row:last-child { border-bottom: none; }
        .pos-search-result-row:hover { background: #f8f9fb; }
        .pos-search-result-name { font-weight: 600; font-size: 13.5px; }
        .pos-search-result-meta { font-size: 12px; color: #888; margin-top: 1px; }
        .pos-stock-pill {
          font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 20px; white-space: nowrap;
        }
        .pos-stock-pill.in { background: #d1f5d3; color: #14532d; }
        .pos-stock-pill.out { background: #fee2e2; color: #7f1d1d; }

        /* --- cart --- */
        .pos-cart-card { min-height: 120px; }
        .pos-cart-total-pill {
          font-size: 12.5px; font-weight: 700; color: #1c1c1e; background: #f0fdf4;
          border: 1px solid #bbf7d0; padding: 4px 12px; border-radius: 20px;
        }

        .pos-empty-state {
          display: flex; flex-direction: column; align-items: center; justify-content: center;
          padding: 34px 10px; color: #999; text-align: center;
        }
        .pos-empty-icon { font-size: 30px; margin-bottom: 8px; opacity: 0.6; }
        .pos-empty-title { font-weight: 600; font-size: 14px; color: #555; }
        .pos-empty-sub { font-size: 12.5px; margin-top: 2px; }

        .pos-cart-row {
          display: flex; align-items: center; gap: 14px; padding: 12px 4px;
          border-bottom: 1px solid #f0f0f0;
        }
        .pos-cart-row:last-of-type { border-bottom: none; }
        .pos-cart-row-main { flex: 1; min-width: 0; }
        .pos-cart-row-name { font-weight: 600; font-size: 14px; }
        .pos-cart-row-meta { font-size: 12px; color: #888; margin-top: 2px; }
        .pos-cart-row-mrp { color: #555; }

        .pos-qty-stepper {
          display: flex; align-items: center; border: 1px solid #ddd; border-radius: 8px;
          overflow: hidden; flex-shrink: 0;
        }
        .pos-qty-stepper input {
          width: 52px; text-align: center; border: none; border-radius: 0;
          padding: 6px 2px; -moz-appearance: textfield;
        }
        .pos-qty-stepper input::-webkit-outer-spin-button,
        .pos-qty-stepper input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
        .pos-qty-btn {
          background: #f5f5f5; color: #1c1c1e; border: none; width: 28px; height: 34px;
          font-size: 16px; font-weight: 700; cursor: pointer; padding: 0; border-radius: 0;
          transition: background 0.12s ease;
        }
        .pos-qty-btn:hover { background: #e8e8e8; }

        .pos-remove-btn {
          width: 30px; height: 30px; padding: 0; border-radius: 8px; flex-shrink: 0;
          font-size: 13px; color: #888;
        }
        .pos-remove-btn:hover { background: #fee2e2; color: #b91c1c; }

        .pos-checking-text {
          display: flex; align-items: center; gap: 8px;
          color: #888; font-size: 13px; margin: 10px 0 0;
        }
        .pos-checking-spinner {
          width: 12px; height: 12px; border: 2px solid #e5e5e5; border-top-color: #999;
          border-radius: 50%; animation: posSpin 0.7s linear infinite;
        }
        @keyframes posSpin { to { transform: rotate(360deg); } }

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

        .pos-checkout-row {
          display: flex; justify-content: space-between; align-items: center;
          margin-top: 16px; padding-top: 14px; border-top: 1px solid #f0f0f0;
        }
        .pos-checkout-summary { display: flex; flex-direction: column; }
        .pos-checkout-label { font-size: 11px; color: #999; text-transform: uppercase; letter-spacing: 0.4px; }
        .pos-checkout-value { font-size: 20px; font-weight: 700; color: #1c1c1e; }
        .pos-complete-btn {
          padding: 12px 22px; font-size: 14.5px; font-weight: 600; border-radius: 10px;
          background: linear-gradient(135deg, #1c1c1e, #34343a);
          box-shadow: 0 2px 8px rgba(0,0,0,0.18);
          transition: transform 0.12s ease, box-shadow 0.12s ease;
        }
        .pos-complete-btn:hover:not(:disabled) {
          transform: translateY(-1px); box-shadow: 0 4px 14px rgba(0,0,0,0.24);
        }
        .pos-complete-btn:disabled { opacity: 0.5; cursor: not-allowed; }

        .pos-success-card {
          display: flex; align-items: center; gap: 12px; border-left: 4px solid #16a34a;
          color: #14532d; font-weight: 600; background: #f0fdf4;
        }
        .pos-success-sub { font-size: 12px; font-weight: 400; color: #3f6212; margin-top: 2px; }
        .pos-success-check {
          width: 30px; height: 30px; border-radius: 50%; background: #16a34a; color: #fff;
          display: flex; align-items: center; justify-content: center; font-size: 15px; flex-shrink: 0;
        }
        .pos-success-dismiss { margin-left: auto; font-size: 12px; padding: 6px 12px; flex-shrink: 0; }
      `}</style>
    </div>
  );
}