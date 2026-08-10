import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ShoppingCart, Search, User, UserPlus, AlertTriangle, AlertCircle, Info, CheckCircle, X, Trash2, Maximize, Minimize } from "lucide-react";
import { api } from "../api/client.js";

const SEVERITY_META = {
  high: { color: "var(--danger)", bg: "rgba(220, 38, 38, 0.1)", border: "var(--danger)", label: "High risk", icon: <AlertCircle size={16} /> },
  medium: { color: "var(--warning)", bg: "rgba(202, 138, 4, 0.1)", border: "var(--warning)", label: "Medium risk", icon: <AlertTriangle size={16} /> },
  low: { color: "var(--info)", bg: "rgba(2, 132, 199, 0.1)", border: "var(--info)", label: "Low risk", icon: <Info size={16} /> },
  unknown: { color: "var(--text-muted)", bg: "var(--bg-surface)", border: "var(--border)", label: "Flagged", icon: <AlertTriangle size={16} /> },
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
        <span className="pos-search-icon"><Search size={16} /></span>
        <input
          className="pos-search-input"
          placeholder="Search medicine to add to cart..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{ background: "var(--bg-surface)", color: "var(--text-main)", borderColor: "var(--border)" }}
        />
        {searching && <span className="pos-search-spinner" />}
      </div>
      {results.length > 0 && (
        <div className="pos-search-results" style={{ background: "var(--bg-card)", borderColor: "var(--border)" }}>
          {results.map((m, i) => (
            <div
              key={m.id}
              className="pos-search-result-row"
              style={{ animationDelay: `${Math.min(i * 30, 200)}ms`, borderColor: "var(--border)" }}
              onClick={() => { onAdd(m); setQuery(""); setResults([]); }}
            >
              <div className="pos-search-result-main">
                <div className="pos-search-result-name" style={{ color: "var(--text-main)" }}>{m.particulars}</div>
                <div className="pos-search-result-meta" style={{ color: "var(--text-muted)" }}>
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
// Quantity stepper
// ---------------------------------------------------------------------------
function QtyStepper({ qty, onChange }) {
  const step = 1;
  function bump(delta) {
    const next = Math.max(0, Math.round((Number(qty || 0) + delta) * 100) / 100);
    onChange(next);
  }
  return (
    <div className="pos-qty-stepper" style={{ borderColor: "var(--border)" }}>
      <button type="button" className="pos-qty-btn" onClick={() => bump(-step)} style={{ background: "var(--bg-surface)", color: "var(--text-main)" }}>−</button>
      <input
        type="number" min="0" step="0.01"
        value={qty}
        onChange={(e) => onChange(Number(e.target.value) || 0)}
        style={{ background: "var(--bg-card)", color: "var(--text-main)" }}
      />
      <button type="button" className="pos-qty-btn" onClick={() => bump(step)} style={{ background: "var(--bg-surface)", color: "var(--text-main)" }}>+</button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Customer picker (Pillar 5) — optional, attaches this sale to a customer
// profile and unlocks the "credit / udhaar" payment mode.
// ---------------------------------------------------------------------------
function CustomerPicker({ customer, onSelect, onClear }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (query.trim().length < 2) { setResults([]); return; }
    const t = setTimeout(() => api.searchCustomers(query).then(setResults), 250);
    return () => clearTimeout(t);
  }, [query]);

  async function handleQuickAdd() {
    if (query.trim().length < 6) return;
    setCreating(true);
    try {
      const c = await api.createOrGetCustomer({ phone: query.trim() });
      onSelect(c);
      setQuery(""); setResults([]);
    } finally { setCreating(false); }
  }

  if (customer) {
    return (
      <div className="pos-customer-chip" style={{ background: "var(--bg-surface)", borderColor: "var(--border)" }}>
        <span className="pos-customer-chip-icon"><User size={20} color="var(--primary-500)" /></span>
        <div>
          <div className="pos-customer-chip-name" style={{ color: "var(--text-main)" }}>{customer.name || "Unnamed"}</div>
          <div className="pos-customer-chip-phone" style={{ color: "var(--text-muted)" }}>{customer.phone}{customer.current_balance > 0 ? ` · owes ${formatMoney(customer.current_balance)}` : ""}</div>
        </div>
        <button className="btn btn-secondary pos-customer-chip-clear" onClick={onClear}>Change</button>
      </div>
    );
  }

  return (
    <div className="pos-customer-picker">
      <input
        placeholder="Customer phone or name (optional — for udhaar/credit)"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        style={{ background: "var(--bg-surface)", color: "var(--text-main)", borderColor: "var(--border)" }}
      />
      {results.length > 0 && (
        <div className="pos-search-results" style={{ background: "var(--bg-card)", borderColor: "var(--border)" }}>
          {results.map((c) => (
            <div key={c.customer_id} className="pos-search-result-row" onClick={() => { onSelect(c); setQuery(""); setResults([]); }} style={{ borderColor: "var(--border)" }}>
              <div className="pos-search-result-main">
                <div className="pos-search-result-name" style={{ color: "var(--text-main)" }}>{c.name || "Unnamed"}</div>
                <div className="pos-search-result-meta" style={{ color: "var(--text-muted)" }}>{c.phone}</div>
              </div>
              {c.current_balance > 0 && <span className="pos-stock-pill out">{formatMoney(c.current_balance)} due</span>}
            </div>
          ))}
        </div>
      )}
      {results.length === 0 && query.trim().length >= 6 && (
        <button className="btn btn-secondary pos-customer-quickadd" onClick={handleQuickAdd} disabled={creating} style={{ display: "flex", alignItems: "center", gap: 6, justifyContent: "center" }}>
          <UserPlus size={16} />
          {creating ? "Adding..." : `Add "${query.trim()}" as new customer`}
        </button>
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
        <span className="pos-warning-icon" style={{ color: meta.color }}>{meta.icon}</span>
        <strong style={{ color: meta.color }}>Possible drug interaction in this cart</strong>
      </div>
      {interactions.map((i, idx) => {
        const m = SEVERITY_META[i.severity] || SEVERITY_META.unknown;
        return (
          <div key={idx} className="pos-warning-row" style={{ borderColor: "rgba(128,128,128,0.2)" }}>
            <span className="pos-warning-pair" style={{ color: "var(--text-main)" }}>{i.salt_a} + {i.salt_b}</span>
            <span className="pos-warning-severity" style={{ color: m.color }}>{m.label}</span>
            {i.note && <div className="pos-warning-note" style={{ color: "var(--text-muted)" }}>{i.note}</div>}
          </div>
        );
      })}
      <p className="pos-warning-disclaimer" style={{ color: "var(--text-muted)" }}>
        This only flags a known composition-level interaction — it is not a diagnosis or dosing
        instruction. Use your own pharmacist judgment; if you're confident this combination is
        appropriate for this customer, confirm below to proceed.
      </p>
      {onAcknowledge && (
        <button className="btn btn-secondary pos-override-btn" onClick={onAcknowledge} disabled={acknowledging}>
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
      <div className="pos-empty-icon"><ShoppingCart size={32} color="var(--text-muted)" /></div>
      <div className="pos-empty-title" style={{ color: "var(--text-main)" }}>Cart is empty</div>
      <div className="pos-empty-sub" style={{ color: "var(--text-muted)" }}>Search for a medicine above to start building this sale.</div>
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
  const [customer, setCustomer] = useState(null);
  const [paymentMode, setPaymentMode] = useState("cash");
  const [focusMode, setFocusMode] = useState(false);
  const topRef = useRef(null);

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

  function handleClearCustomer() {
    setCustomer(null);
    setPaymentMode("cash");
  }

  async function submitCart(confirmOverride = false) {
    setError(null);
    setSubmitting(true);
    try {
      const res = await api.recordCartSale(
        cart.map((c) => ({ medicine_id: c.medicine.id, qty_sold: c.qty })),
        confirmOverride,
        customer ? customer.customer_id : null,
        customer ? paymentMode : "cash",
      );
      if (res.status === "needs_confirmation") {
        setCheckResult(res);
      } else {
        const creditNote = res.payment_mode === "credit" && res.credit_balance_after != null
          ? ` Charged to ${customer.name || customer.phone}'s udhaar — new balance ${formatMoney(res.credit_balance_after)}.`
          : "";
        setSuccess(`Sale recorded — ${cart.length} item${cart.length === 1 ? "" : "s"} sold (${formatMoney(res.total_value)}).${creditNote}`);
        setCart([]);
        setCheckResult(null);
        setCustomer(null);
        setPaymentMode("cash");
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

  const focusStyles = focusMode ? {
    position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
    zIndex: 9999, background: "var(--bg-app)", overflowY: "auto",
    padding: "32px 10%", 
    boxShadow: "0 0 100px rgba(0,0,0,0.5)"
  } : {};

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0, ...focusStyles }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.4, ease: "easeInOut" }}
      className="page-content"
      style={focusMode ? { height: "100vh" } : {}}
    >
      <div ref={topRef} />

      {success && (
        <div className="card pos-success-card pos-fade-in" style={{ borderColor: "var(--success)" }}>
          <span className="pos-success-check"><CheckCircle size={24} color="var(--success)" /></span>
          <div>
            <div style={{ color: "var(--text-main)", fontWeight: 600 }}>{success}</div>
            <div className="pos-success-sub" style={{ color: "var(--text-muted)" }}>Stock levels and the sales ledger have been updated.</div>
          </div>
          <button className="btn btn-secondary pos-success-dismiss" onClick={() => setSuccess(null)}>Dismiss</button>
        </div>
      )}

      <div className="card pos-header-card" style={{ background: "var(--bg-card)", position: "relative" }}>
        <button 
          onClick={() => setFocusMode(!focusMode)} 
          className="btn btn-secondary" 
          style={{ position: "absolute", top: 16, right: 16, padding: "8px 12px" }}
        >
          {focusMode ? <><Minimize size={16} /> Exit Focus Mode</> : <><Maximize size={16} /> Focus Mode</>}
        </button>
        <h2 style={{ marginBottom: 4, display: "flex", alignItems: "center", gap: 8, color: "var(--text-main)" }}>
          <ShoppingCart size={24} color="var(--primary-500)" /> Point of Sale
        </h2>
        <p style={{ color: "var(--text-muted)", fontSize: 13, marginTop: 0 }}>
          Add every medicine a customer is buying in this visit to the cart — as soon as there are
          2 or more items, they're automatically checked against each other for known drug
          interactions before the sale is recorded. Attach a customer profile below to sell on
          credit (udhaar) instead of cash.
        </p>
        <MedicineSearch onAdd={addToCart} excludeIds={cartIds} />
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0, marginBottom: 10, fontSize: 15, display: "flex", alignItems: "center", gap: 8, color: "var(--text-main)" }}>
          <User size={18} color="var(--info)" /> Customer (optional)
        </h3>
        <CustomerPicker customer={customer} onSelect={setCustomer} onClear={handleClearCustomer} />
        {customer && (
          <div className="pos-payment-toggle">
            <label className={paymentMode === "cash" ? "active" : ""} style={{ borderColor: "var(--border)", color: "var(--text-main)" }}>
              <input type="radio" name="payment-mode" checked={paymentMode === "cash"} onChange={() => setPaymentMode("cash")} />
              💵 Cash
            </label>
            <label className={paymentMode === "credit" ? "active" : ""} style={{ borderColor: "var(--border)", color: "var(--text-main)" }}>
              <input type="radio" name="payment-mode" checked={paymentMode === "credit"} onChange={() => setPaymentMode("credit")} />
              📒 Credit (udhaar)
            </label>
          </div>
        )}
      </div>

      <div className="card pos-cart-card">
        <div className="flex-between" style={{ marginBottom: cart.length ? 10 : 0 }}>
          <h3 style={{ margin: 0, color: "var(--text-main)" }}>Cart {cart.length > 0 && `(${cart.length})`}</h3>
          {cart.length > 0 && (
            <span className="pos-cart-total-pill" style={{ background: "var(--bg-surface)", borderColor: "var(--border)", color: "var(--text-main)" }}>
              {totalUnits} unit{totalUnits === 1 ? "" : "s"} · {formatMoney(cartTotal)}
            </span>
          )}
        </div>

        {cart.length === 0 && <EmptyCartState />}

        {cart.map((c) => (
          <div key={c.medicine.id} className="pos-cart-row pos-fade-in" style={{ borderColor: "var(--border)" }}>
            <div className="pos-cart-row-main">
              <div className="pos-cart-row-name" style={{ color: "var(--text-main)" }}>{c.medicine.particulars}</div>
              <div className="pos-cart-row-meta" style={{ color: "var(--text-muted)" }}>
                {c.medicine.composition || "No composition data"}
                {c.medicine.mrp != null && <span className="pos-cart-row-mrp"> · {formatMoney(c.medicine.mrp)} each</span>}
              </div>
            </div>
            <QtyStepper qty={c.qty} onChange={(v) => updateQty(c.medicine.id, v)} />
            <button className="btn btn-secondary pos-remove-btn" onClick={() => removeFromCart(c.medicine.id)} title="Remove item" style={{ padding: 4 }}>
              <Trash2 size={16} color="var(--danger)" />
            </button>
          </div>
        ))}

        {checking && (
          <p className="pos-checking-text" style={{ color: "var(--text-muted)" }}>
            <span className="pos-checking-spinner" style={{ borderColor: "var(--border)", borderTopColor: "var(--text-main)" }} /> Checking for interactions...
          </p>
        )}

        <InteractionWarning
          interactions={checkResult?.interactions}
          onAcknowledge={() => submitCart(true)}
          acknowledging={submitting}
        />

        {error && <p style={{ color: "var(--danger)", fontSize: 13, marginTop: 10 }}>{error}</p>}

        {cart.length > 0 && !hasBlockingWarning && (
          <div className="pos-checkout-row" style={{ borderColor: "var(--border)" }}>
            <div className="pos-checkout-summary">
              <span className="pos-checkout-label" style={{ color: "var(--text-muted)" }}>Total {customer && paymentMode === "credit" ? "(on credit)" : ""}</span>
              <span className="pos-checkout-value" style={{ color: "var(--text-main)" }}>{formatMoney(cartTotal)}</span>
            </div>
            <button
              className="btn btn-primary pos-complete-btn"
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

        /* --- search --- */
        .pos-search-wrap { position: relative; }
        .pos-search-input-wrap { position: relative; display: flex; align-items: center; }
        .pos-search-icon { position: absolute; left: 12px; opacity: 0.5; pointer-events: none; }
        .pos-search-input {
          width: 100%; padding-left: 36px !important; padding-top: 10px; padding-bottom: 10px;
          border: 1.5px solid var(--border); transition: border-color 0.15s ease, box-shadow 0.15s ease;
        }
        .pos-search-input:focus { outline: none; border-color: var(--primary-500); box-shadow: 0 0 0 3px rgba(14,165,233,0.15); }
        .pos-search-spinner {
          position: absolute; right: 12px; width: 14px; height: 14px;
          border: 2px solid var(--border); border-top-color: var(--primary-500); border-radius: 50%;
          animation: posSpin 0.7s linear infinite;
        }
        .pos-search-results {
          margin-top: 8px; border: 1px solid var(--border); border-radius: 10px; overflow: hidden;
          box-shadow: 0 4px 16px rgba(0,0,0,0.06);
        }
        .pos-search-result-row {
          display: flex; justify-content: space-between; align-items: center;
          padding: 10px 14px; cursor: pointer; border-bottom: 1px solid var(--border);
          opacity: 0; animation: posFadeInRow 0.25s ease forwards;
          transition: background 0.12s ease;
        }
        .pos-search-result-row:last-child { border-bottom: none; }
        .pos-search-result-row:hover { background: var(--bg-surface); }
        .pos-search-result-name { font-weight: 600; font-size: 13.5px; }
        .pos-search-result-meta { font-size: 12px; margin-top: 1px; }
        .pos-stock-pill { font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 20px; white-space: nowrap; }
        .pos-stock-pill.in { background: rgba(34, 197, 94, 0.1); color: var(--success); }
        .pos-stock-pill.out { background: rgba(239, 68, 68, 0.1); color: var(--danger); }

        /* --- customer picker --- */
        .pos-customer-picker { position: relative; }
        .pos-customer-picker > input { width: 100%; }
        .pos-customer-quickadd { width: 100%; margin-top: 8px; text-align: left; }
        .pos-customer-chip {
          display: flex; align-items: center; gap: 10px; border: 1px solid var(--border);
          border-radius: 10px; padding: 10px 12px;
        }
        .pos-customer-chip-icon { display: flex; }
        .pos-customer-chip-name { font-weight: 600; font-size: 13.5px; }
        .pos-customer-chip-phone { font-size: 12px; }
        .pos-customer-chip-clear { margin-left: auto; font-size: 12px; padding: 6px 12px; }
        .pos-payment-toggle { display: flex; gap: 8px; margin-top: 10px; }
        .pos-payment-toggle label {
          flex: 1; text-align: center; padding: 8px; border: 1.5px solid var(--border); border-radius: 8px;
          font-size: 13px; cursor: pointer; transition: all 0.15s ease;
        }
        .pos-payment-toggle label.active { border-color: var(--primary-500); background: var(--primary-500); color: #fff !important; font-weight: 600; }
        .pos-payment-toggle input { display: none; }

        /* --- cart --- */
        .pos-cart-card { min-height: 120px; }
        .pos-cart-total-pill {
          font-size: 12.5px; font-weight: 700; padding: 4px 12px; border-radius: 20px; border: 1px solid var(--border);
        }
        .pos-empty-state { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 34px 10px; text-align: center; }
        .pos-empty-icon { margin-bottom: 8px; opacity: 0.6; }
        .pos-empty-title { font-weight: 600; font-size: 14px; }
        .pos-empty-sub { font-size: 12.5px; margin-top: 2px; }

        .pos-cart-row { display: flex; align-items: center; gap: 14px; padding: 12px 4px; border-bottom: 1px solid var(--border); }
        .pos-cart-row:last-of-type { border-bottom: none; }
        .pos-cart-row-main { flex: 1; min-width: 0; }
        .pos-cart-row-name { font-weight: 600; font-size: 14px; }
        .pos-cart-row-meta { font-size: 12px; margin-top: 2px; }

        .pos-qty-stepper { display: flex; align-items: center; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; flex-shrink: 0; }
        .pos-qty-stepper input { width: 52px; text-align: center; border: none; border-radius: 0; padding: 6px 2px; -moz-appearance: textfield; }
        .pos-qty-stepper input::-webkit-outer-spin-button, .pos-qty-stepper input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
        .pos-qty-btn { border: none; width: 28px; height: 34px; font-size: 16px; font-weight: 700; cursor: pointer; padding: 0; border-radius: 0; transition: background 0.12s ease; }
        .pos-qty-btn:hover { opacity: 0.8; }

        .pos-remove-btn { display: flex; align-items: center; justify-content: center; width: 34px; height: 34px; border-radius: 8px; flex-shrink: 0; }
        .pos-remove-btn:hover { background: rgba(239, 68, 68, 0.1) !important; border-color: rgba(239, 68, 68, 0.2); }

        .pos-checking-text { display: flex; align-items: center; gap: 8px; font-size: 13px; margin: 10px 0 0; }
        .pos-checking-spinner { width: 12px; height: 12px; border: 2px solid; border-radius: 50%; animation: posSpin 0.7s linear infinite; }
        @keyframes posSpin { to { transform: rotate(360deg); } }

        .pos-warning-banner { border: 1px solid; border-radius: 12px; padding: 14px 16px; margin-top: 14px; animation: posFadeIn 0.25s ease; }
        .pos-warning-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; font-size: 14px; }
        .pos-warning-icon { display: flex; }
        .pos-warning-row { padding: 6px 0; border-top: 1px solid; }
        .pos-warning-pair { font-weight: 600; font-size: 13px; }
        .pos-warning-severity { font-size: 11px; font-weight: 700; margin-left: 8px; text-transform: uppercase; }
        .pos-warning-note { font-size: 12.5px; margin-top: 3px; }
        .pos-warning-disclaimer { font-size: 12px; margin: 10px 0 0; line-height: 1.5; }
        .pos-override-btn { margin-top: 10px; }

        .pos-checkout-row { display: flex; justify-content: space-between; align-items: center; margin-top: 16px; padding-top: 14px; border-top: 1px solid; }
        .pos-checkout-summary { display: flex; flex-direction: column; }
        .pos-checkout-label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.4px; }
        .pos-checkout-value { font-size: 20px; font-weight: 700; }
        .pos-complete-btn { padding: 12px 22px; font-size: 14.5px; font-weight: 600; border-radius: 10px; }
        .pos-complete-btn:disabled { opacity: 0.5; cursor: not-allowed; }

        .pos-success-card { display: flex; align-items: center; gap: 12px; border-left: 4px solid; background: rgba(34, 197, 94, 0.05); }
        .pos-success-sub { font-size: 12px; font-weight: 400; margin-top: 2px; }
        .pos-success-check { display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
        .pos-success-dismiss { margin-left: auto; font-size: 12px; padding: 6px 12px; flex-shrink: 0; }
      `}</style>
    </motion.div>
  );
}