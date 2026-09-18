import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { User, Bell, MessageSquare, AlertTriangle, UserPlus, CreditCard, Clock, Activity, Send } from "lucide-react";
import { api } from "../api/client.js";

function formatMoney(n) {
  if (n == null) return "₹0";
  return "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function timeAgo(iso) {
  if (!iso) return "—";
  const diffMs = Date.now() - new Date(iso).getTime();
  const days = Math.floor(diffMs / 86400000);
  if (days < 1) return "today";
  if (days === 1) return "1 day ago";
  return `${days} days ago`;
}

// ---------------------------------------------------------------------------
// Tab 1: Directory & Credit
// ---------------------------------------------------------------------------
function NewCustomerForm({ onCreated }) {
  const [phone, setPhone] = useState("");
  const [name, setName] = useState("");
  const [consent, setConsent] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const customer = await api.createOrGetCustomer({ phone, name: name || null, consent_given: consent });
      setPhone(""); setName(""); setConsent(false);
      onCreated(customer);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="cust-new-form" style={{ marginTop: 12 }}>
      <input placeholder="Phone number" value={phone} onChange={(e) => setPhone(e.target.value)} required style={{ flex: 1, minWidth: 150, padding: "8px 12px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-surface)", color: "var(--text-main)" }} />
      <input placeholder="Name (optional)" value={name} onChange={(e) => setName(e.target.value)} style={{ flex: 1, minWidth: 150, padding: "8px 12px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-surface)", color: "var(--text-main)" }} />
      <label className="cust-consent-label" style={{ color: "var(--text-muted)" }}>
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        Adherence tracking consent
      </label>
      <button type="submit" className="btn btn-primary" disabled={saving} style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <UserPlus size={16} />
        {saving ? "Saving..." : "Add / find"}
      </button>
      {error && <span style={{ color: "var(--danger)", fontSize: 12.5 }}>{error}</span>}
    </form>
  );
}

function CustomerDetail({ customer, onChanged }) {
  const [ledger, setLedger] = useState([]);
  const [loading, setLoading] = useState(true);
  const [chargeAmount, setChargeAmount] = useState("");
  const [chargeNote, setChargeNote] = useState("");
  const [paymentAmount, setPaymentAmount] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const refresh = useCallback(() => {
    let active = true;
    setLoading(true);
    api.getCustomerLedger(customer.customer_id)
      .then(data => {
        if (active) setLedger(data.items || data);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [customer.customer_id]);

  useEffect(() => {
    const cancel = refresh();
    return cancel;
  }, [refresh]);

  async function handleCharge() {
    if (!chargeAmount) return;
    setBusy(true); setError(null);
    try {
      const updated = await api.chargeCustomerCredit(customer.customer_id, Number(chargeAmount), chargeNote || null);
      setChargeAmount(""); setChargeNote("");
      refresh();
      onChanged(updated);
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }

  async function handlePayment() {
    if (!paymentAmount) return;
    setBusy(true); setError(null);
    try {
      const updated = await api.recordCustomerPayment(customer.customer_id, Number(paymentAmount), "Payment received");
      setPaymentAmount("");
      refresh();
      onChanged(updated);
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }

  return (
    <div className="card cust-detail-card" style={{ borderColor: "var(--primary-500)" }}>
      <div className="flex-between">
        <div>
          <h3 style={{ margin: 0, color: "var(--text-main)", display: "flex", alignItems: "center", gap: 8 }}>
            <User size={20} color="var(--info)" />
            {customer.name || "Unnamed customer"}
          </h3>
          <div style={{ fontSize: 12.5, color: "var(--text-muted)", marginTop: 4 }}>
            {customer.phone} · {customer.total_purchases} purchase(s) · last visit {timeAgo(customer.last_visit)}
          </div>
        </div>
        <span className={`cust-balance-pill ${customer.current_balance > 0 ? "owed" : "clear"}`}>
          {customer.current_balance > 0 ? `Owes ${formatMoney(customer.current_balance)}` : "No balance due"}
        </span>
      </div>

      {!customer.consent_given_at && (
        <p className="cust-consent-note" style={{ background: "rgba(202, 138, 4, 0.1)", color: "var(--warning)" }}>
          <AlertTriangle size={14} style={{ display: "inline", marginBottom: -2, marginRight: 4 }} />
          No adherence-tracking consent on file for this customer — their purchases won't appear in Adherence Alerts.
        </p>
      )}

      <div className="cust-credit-actions">
        <div className="cust-credit-action">
          <label style={{ color: "var(--text-muted)" }}>Charge to udhaar</label>
          <div style={{ display: "flex", gap: 6 }}>
            <input type="number" min="0.01" step="0.01" placeholder="Amount" value={chargeAmount} onChange={(e) => setChargeAmount(e.target.value)} style={{ width: 90, padding: "8px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-surface)", color: "var(--text-main)" }} />
            <input placeholder="Note (optional)" value={chargeNote} onChange={(e) => setChargeNote(e.target.value)} style={{ flex: 1, padding: "8px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-surface)", color: "var(--text-main)" }} />
            <button className="btn btn-secondary" onClick={handleCharge} disabled={busy || !chargeAmount}>Charge</button>
          </div>
        </div>
        <div className="cust-credit-action">
          <label style={{ color: "var(--text-muted)" }}>Record payment received</label>
          <div style={{ display: "flex", gap: 6 }}>
            <input type="number" min="0.01" step="0.01" placeholder="Amount" value={paymentAmount} onChange={(e) => setPaymentAmount(e.target.value)} style={{ width: 90, padding: "8px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-surface)", color: "var(--text-main)" }} />
            <button className="btn btn-secondary" onClick={handlePayment} disabled={busy || !paymentAmount}>Record payment</button>
          </div>
        </div>
      </div>
      {error && <p style={{ color: "var(--danger)", fontSize: 13 }}>{error}</p>}

      <h4 style={{ marginBottom: 6, color: "var(--text-main)" }}>Ledger</h4>
      {loading && <p style={{ color: "var(--text-muted)", fontSize: 13 }}>Loading...</p>}
      {!loading && ledger.length === 0 && <p style={{ color: "var(--text-muted)", fontSize: 13 }}>No credit activity yet.</p>}
      {!loading && ledger.length > 0 && (
        <table className="table">
          <thead><tr><th>Date</th><th>Type</th><th>Change</th><th>Balance after</th><th>Note</th></tr></thead>
          <tbody>
            {ledger.map((e) => (
              <tr key={e.id}>
                <td>{new Date(e.created_at).toLocaleDateString()}</td>
                <td><span className={`badge ${e.reason === "payment_received" ? "auto" : "manual"}`}>{e.reason.replace("_", " ")}</span></td>
                <td style={{ color: e.change_amount > 0 ? "var(--danger)" : "var(--success)" }}>{e.change_amount > 0 ? "+" : ""}{formatMoney(e.change_amount)}</td>
                <td>{formatMoney(e.resulting_balance)}</td>
                <td style={{ color: "var(--text-muted)" }}>{e.note || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function DirectoryTab() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [selected, setSelected] = useState(null);
  const [outstanding, setOutstanding] = useState([]);

  function refreshOutstanding() {
    api.getOutstandingBalances().then(setOutstanding);
  }
  useEffect(() => { refreshOutstanding(); }, []);

  useEffect(() => {
    if (query.trim().length < 2) { setResults([]); return; }
    const t = setTimeout(() => api.searchCustomers(query).then(data => setResults(data.items || data)), 250);
    return () => clearTimeout(t);
  }, [query]);

  function handleCreated(customer) {
    setSelected(customer);
    refreshOutstanding();
  }

  function handleChanged(customer) {
    setSelected(customer);
    refreshOutstanding();
  }

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} transition={{ duration: 0.2 }}>
      <div className="card">
        <h3 style={{ marginTop: 0, color: "var(--text-main)" }}>Find or add a customer</h3>
        <input
          style={{ width: "100%", marginBottom: 10, padding: "8px 12px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-surface)", color: "var(--text-main)" }}
          placeholder="Search by phone or name..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        {results.length > 0 && (
          <table className="table" style={{ marginBottom: 10 }}>
            <tbody>
              {results.map((c) => (
                <tr key={c.customer_id} style={{ cursor: "pointer" }} onClick={() => setSelected(c)}>
                  <td>{c.name || "Unnamed"}</td>
                  <td style={{ color: "var(--text-muted)" }}>{c.phone}</td>
                  <td>{c.current_balance > 0 ? <span className="badge unmatched">{formatMoney(c.current_balance)} due</span> : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <NewCustomerForm onCreated={handleCreated} />
      </div>

      {selected && <CustomerDetail customer={selected} onChanged={handleChanged} />}

      <div className="card">
        <h3 style={{ marginTop: 0, display: "flex", alignItems: "center", gap: 8, color: "var(--text-main)" }}>
          <CreditCard size={20} color="var(--orange)" /> Outstanding udhaar balances
        </h3>
        {outstanding.length === 0 ? (
          <p style={{ color: "var(--text-muted)", fontSize: 13 }}>Nobody currently owes the shop money. 🎉</p>
        ) : (
          <table className="table">
            <thead><tr><th>Customer</th><th>Phone</th><th>Balance</th></tr></thead>
            <tbody>
              {outstanding.map((o) => (
                <tr key={o.customer_id} style={{ cursor: "pointer" }} onClick={() => setSelected({ customer_id: o.customer_id, phone: o.phone, name: o.name, current_balance: o.current_balance, total_purchases: 0, last_visit: null, consent_given_at: null })}>
                  <td>{o.name || "Unnamed"}</td>
                  <td style={{ color: "var(--text-muted)" }}>{o.phone}</td>
                  <td style={{ color: "var(--danger)", fontWeight: 600 }}>{formatMoney(o.current_balance)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Tab 2: Adherence Alerts
// ---------------------------------------------------------------------------
function AdherenceTab() {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.getAdherenceAlerts()
      .then(setAlerts)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} transition={{ duration: 0.2 }}>
      <div className="card">
        <h3 style={{ marginTop: 0, display: "flex", alignItems: "center", gap: 8, color: "var(--text-main)" }}>
          <Clock size={20} color="var(--warning)" /> Overdue refill alerts
        </h3>
        <p style={{ color: "var(--text-muted)", fontSize: 13 }}>
          Customers with a regular repeat-purchase pattern for a specific medicine who are now past
          their usual refill gap — a candidate list to proactively call, not a diagnosis. Only
          includes customers who've given adherence-tracking consent.
        </p>
        {loading && <p style={{ color: "var(--text-muted)", fontSize: 13 }}>Loading...</p>}
        {error && <p style={{ color: "var(--danger-700)", fontSize: 13 }}>Failed to load alerts: {error}</p>}
        {!loading && !error && alerts.length === 0 && (
          <p style={{ color: "var(--text-muted)", fontSize: 13 }}>No overdue refills detected right now.</p>
        )}
        {!loading && alerts.map((a, i) => (
          <div key={i} className="reorder-item-row" style={{ borderBottom: "1px solid var(--border)", padding: "12px 0", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <div className="reorder-item-name" style={{ fontWeight: 600, color: "var(--text-main)" }}>{a.customer_name || a.customer_phone} — {a.medicine_name}</div>
              <div className="reorder-item-meta" style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>
                Usual gap ~{a.avg_gap_days} days · last bought {timeAgo(a.last_purchase_date)} · {a.purchase_count} purchases on record
              </div>
            </div>
            <span className="badge unmatched">{Math.round(a.days_overdue)} days overdue</span>
          </div>
        ))}
      </div>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Tab 3: Symptom Bot
// ---------------------------------------------------------------------------
function SymptomBotTab() {
  const [message, setMessage] = useState("");
  const [history, setHistory] = useState([]);
  const [asking, setAsking] = useState(false);

  async function handleAsk(e) {
    e.preventDefault();
    if (!message.trim()) return;
    const userMsg = message;
    setMessage("");
    setHistory((h) => [...h, { role: "user", text: userMsg }]);
    setAsking(true);
    try {
      const res = await api.querySymptomBot(userMsg);
      setHistory((h) => [...h, { role: "bot", text: res.reply, matched: res.matched }]);
    } catch (err) {
      setHistory((h) => [...h, { role: "bot", text: `Error: ${err.message}`, matched: false }]);
    } finally {
      setAsking(false);
    }
  }

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} transition={{ duration: 0.2 }}>
      <div className="card">
        <h3 style={{ marginTop: 0, display: "flex", alignItems: "center", gap: 8, color: "var(--text-main)" }}>
          <Activity size={20} color="var(--purple)" /> Symptom-to-Stock Bot
        </h3>
        <p style={{ color: "var(--text-muted)", fontSize: 13 }}>
          Type a symptom the way a customer might describe it (e.g. "fever", "bad cough"). This
          checks the shop's live stock against known categories from PharmaGraph — it never
          diagnoses, and always hands off to the pharmacist. This is the same core logic a real
          WhatsApp bot would run behind Twilio's webhook.
        </p>
        <div className="symptom-chat-window" style={{ background: "var(--bg-surface)", borderColor: "var(--border)" }}>
          {history.length === 0 && <div className="symptom-chat-empty" style={{ color: "var(--text-muted)" }}>Try typing "fever" or "cough" to start.</div>}
          {history.map((m, i) => (
            <div key={i} className={`symptom-chat-bubble ${m.role}`} style={m.role === 'user' ? { background: "var(--primary-500)", color: "#fff" } : { background: "var(--bg-card)", borderColor: "var(--border)", color: "var(--text-main)" }}>
              {m.text}
            </div>
          ))}
          {asking && <div className="symptom-chat-bubble bot" style={{ background: "var(--bg-card)", borderColor: "var(--border)", color: "var(--text-main)" }}>Checking stock...</div>}
        </div>
        <form onSubmit={handleAsk} style={{ display: "flex", gap: 8, marginTop: 10 }}>
          <input style={{ flex: 1, padding: "10px 14px", borderRadius: 8, border: "1px solid var(--border)", background: "var(--bg-surface)", color: "var(--text-main)" }} placeholder="Describe the symptom..." value={message} onChange={(e) => setMessage(e.target.value)} />
          <button type="submit" className="btn btn-primary" disabled={asking || !message.trim()} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <Send size={16} /> Send
          </button>
        </form>
      </div>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
export default function Customers() {
  const [tab, setTab] = useState("directory");

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.2 }}
      className="page-content"
    >
      <div className="card">
        <h2 style={{ marginBottom: 4, display: "flex", alignItems: "center", gap: 8, color: "var(--text-main)" }}>
          <User size={24} color="var(--primary-500)" /> Customer Health Companion
        </h2>
        <p style={{ color: "var(--text-muted)", fontSize: 13, marginTop: 0 }}>
          Customer profiles, the udhaar credit ledger, refill-overdue alerts, and a safe
          symptom-to-stock lookup — all built on the same Customer model.
        </p>
        <div className="tabs" style={{ marginBottom: 0, borderBottom: "1px solid var(--border)" }}>
          <button className={`tab-button ${tab === "directory" ? "active" : ""}`} onClick={() => setTab("directory")} style={tab === "directory" ? { borderBottomColor: "var(--primary-500)", color: "var(--primary-500)" } : { color: "var(--text-muted)" }}>
            <User size={16} style={{ display: "inline", marginBottom: -3, marginRight: 4 }} /> Directory & Credit
          </button>
          <button className={`tab-button ${tab === "adherence" ? "active" : ""}`} onClick={() => setTab("adherence")} style={tab === "adherence" ? { borderBottomColor: "var(--primary-500)", color: "var(--primary-500)" } : { color: "var(--text-muted)" }}>
            <Bell size={16} style={{ display: "inline", marginBottom: -3, marginRight: 4 }} /> Adherence Alerts
          </button>
          <button className={`tab-button ${tab === "symptom" ? "active" : ""}`} onClick={() => setTab("symptom")} style={tab === "symptom" ? { borderBottomColor: "var(--primary-500)", color: "var(--primary-500)" } : { color: "var(--text-muted)" }}>
            <MessageSquare size={16} style={{ display: "inline", marginBottom: -3, marginRight: 4 }} /> Symptom Bot
          </button>
        </div>
      </div>

      {tab === "directory" && <DirectoryTab />}
      {tab === "adherence" && <AdherenceTab />}
      {tab === "symptom" && <SymptomBotTab />}

      <style>{`
        .cust-new-form { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
        .cust-consent-label { display: flex; align-items: center; gap: 6px; font-size: 12.5px; white-space: nowrap; }
        .cust-balance-pill { font-size: 12.5px; font-weight: 700; padding: 5px 12px; border-radius: 20px; white-space: nowrap; }
        .cust-balance-pill.owed { background: rgba(239, 68, 68, 0.1); color: var(--danger); }
        .cust-balance-pill.clear { background: rgba(34, 197, 94, 0.1); color: var(--success); }
        .cust-consent-note { font-size: 12.5px; padding: 8px 12px; border-radius: 8px; margin: 10px 0; }
        .cust-credit-actions { display: flex; gap: 16px; flex-wrap: wrap; margin: 14px 0; }
        .cust-credit-action { flex: 1; min-width: 260px; }
        .cust-credit-action label { display: block; font-size: 11px; text-transform: uppercase; margin-bottom: 4px; font-weight: 600; }
        .cust-detail-card { border-left: 4px solid var(--primary-500); }

        .symptom-chat-window {
          border-radius: 10px; padding: 12px;
          min-height: 120px; max-height: 320px; overflow-y: auto; display: flex; flex-direction: column; gap: 8px;
        }
        .symptom-chat-empty { font-size: 13px; text-align: center; padding: 20px 0; }
        .symptom-chat-bubble { max-width: 80%; padding: 8px 12px; border-radius: 12px; font-size: 13px; line-height: 1.5; }
        .symptom-chat-bubble.user { align-self: flex-end; border-bottom-right-radius: 2px; }
        .symptom-chat-bubble.bot { align-self: flex-start; border: 1px solid; border-bottom-left-radius: 2px; }
      `}</style>
    </motion.div>
  );
}