import { useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ShoppingBag, RefreshCw, ChevronDown, ChevronRight, Send,
  AlertTriangle, TrendingUp, Package, DollarSign, Clock,
  CheckCircle, Zap, ArrowUpRight, Phone, X, Loader2, Info
} from "lucide-react";
import { api } from "../api/client.js";

/* ─── Helpers ─────────────────────────────────────────────────────────── */
function fmtMoney(n) {
  if (n == null) return "—";
  return "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}
function fmtQty(n) {
  if (n == null) return "—";
  return Number(n).toLocaleString("en-IN", { maximumFractionDigits: 1 });
}

const PRIORITY_COLORS = {
  high:   { bg: "var(--danger-bg)",   text: "var(--danger-text)",   border: "var(--danger-border)"  },
  medium: { bg: "var(--warning-bg)",  text: "var(--warning-text)",  border: "var(--warning-border)" },
  low:    { bg: "var(--info-bg)",     text: "var(--info-text)",     border: "var(--info-border)"    },
};

/* ─── Stat Card ────────────────────────────────────────────────────────── */
function StatCard({ icon, label, value, sub, color = "var(--primary-600)" }) {
  return (
    <motion.div
      className="card"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      style={{ flex: 1, minWidth: 160 }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
        <div>
          <div style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 6 }}>
            {label}
          </div>
          <div style={{ fontSize: "var(--text-2xl)", fontWeight: 700, color: "var(--text-main)", letterSpacing: "-0.03em" }}>
            {value}
          </div>
          {sub && <div style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)", marginTop: 4 }}>{sub}</div>}
        </div>
        <div style={{ width: 40, height: 40, borderRadius: 10, background: color + "18", display: "flex", alignItems: "center", justifyContent: "center", color }}>
          {icon}
        </div>
      </div>
    </motion.div>
  );
}

/* ─── Priority Badge ───────────────────────────────────────────────────── */
function PriorityBadge({ label }) {
  const c = PRIORITY_COLORS[label] || PRIORITY_COLORS.low;
  return (
    <span style={{
      padding: "2px 8px", borderRadius: 99, fontSize: "var(--text-xs)", fontWeight: 700,
      background: c.bg, color: c.text, border: `1px solid ${c.border}`, textTransform: "uppercase", letterSpacing: "0.05em"
    }}>
      {label}
    </span>
  );
}

/* ─── WhatsApp Modal ───────────────────────────────────────────────────── */
function WhatsAppModal({ group, onClose }) {
  const [phone, setPhone] = useState("+91");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");

  async function handleSend() {
    if (!phone || phone.length < 10) { setError("Enter a valid phone number (e.g. +919876543210)"); return; }
    setLoading(true); setError("");
    try {
      await api.sendSmartPurchaseWhatsApp({
        distributor_name: group.distributor_name,
        phone,
        items: group.items.map(i => ({ medicine_name: i.medicine_name, order_qty: i.order_qty, unit: i.unit || "" }))
      });
      setSent(true);
    } catch (e) {
      setError(e.message || "Failed to send WhatsApp message");
    } finally {
      setLoading(false);
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.94, y: 20 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.94, y: 20 }}
        className="card"
        style={{ maxWidth: 480, width: "100%", padding: 28, position: "relative" }}
        onClick={e => e.stopPropagation()}
      >
        <button onClick={onClose} style={{ position: "absolute", top: 16, right: 16, background: "none", border: "none", cursor: "pointer", color: "var(--text-muted)" }}>
          <X size={18} />
        </button>
        {sent ? (
          <div style={{ textAlign: "center", padding: "20px 0" }}>
            <CheckCircle size={48} color="var(--success-text)" style={{ margin: "0 auto 16px" }} />
            <h3 style={{ marginBottom: 8 }}>Order sent via WhatsApp!</h3>
            <p style={{ color: "var(--text-muted)", fontSize: "var(--text-sm)" }}>
              Purchase order for <strong>{group.distributor_name}</strong> has been sent to {phone}.
            </p>
            <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} className="btn btn-primary" style={{ marginTop: 20 }} onClick={onClose}>
              Close
            </motion.button>
          </div>
        ) : (
          <>
            <h3 style={{ marginBottom: 4, display: "flex", alignItems: "center", gap: 8 }}>
              <Phone size={18} color="var(--primary-600)" /> Send to {group.distributor_name}
            </h3>
            <p style={{ color: "var(--text-muted)", fontSize: "var(--text-sm)", marginBottom: 20 }}>
              Sends a WhatsApp message with {group.items.length} items totalling {fmtMoney(group.total_estimated_cost)}.
            </p>
            <div style={{ background: "var(--bg-app)", borderRadius: "var(--radius-md)", padding: 12, marginBottom: 16, maxHeight: 180, overflowY: "auto" }}>
              {group.items.map((item, i) => (
                <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0", borderBottom: i < group.items.length - 1 ? "1px solid var(--border-subtle)" : "none", fontSize: "var(--text-sm)" }}>
                  <span style={{ fontWeight: 500 }}>{item.medicine_name}</span>
                  <span style={{ color: "var(--text-muted)" }}>{fmtQty(item.order_qty)} {item.unit}</span>
                </div>
              ))}
            </div>
            <label style={{ display: "block", fontSize: "var(--text-sm)", fontWeight: 600, marginBottom: 6 }}>Distributor WhatsApp Number</label>
            <input
              className="input"
              style={{ width: "100%", marginBottom: 8 }}
              placeholder="+919876543210"
              value={phone}
              onChange={e => setPhone(e.target.value)}
            />
            {error && <p style={{ color: "var(--danger-text)", fontSize: "var(--text-sm)", marginBottom: 8 }}>{error}</p>}
            <div style={{ display: "flex", gap: 10, marginTop: 16 }}>
              <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} className="btn btn-secondary" style={{ flex: 1 }} onClick={onClose}>
                Cancel
              </motion.button>
              <motion.button
                whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
                className="btn btn-primary"
                style={{ flex: 2, display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}
                onClick={handleSend}
                disabled={loading}
              >
                {loading ? <Loader2 size={16} className="spin" /> : <Send size={16} />}
                {loading ? "Sending…" : "Send via WhatsApp"}
              </motion.button>
            </div>
          </>
        )}
      </motion.div>
    </motion.div>
  );
}

/* ─── Distributor Group Card ───────────────────────────────────────────── */
function DistributorGroup({ group, idx }) {
  const [open, setOpen] = useState(idx === 0);
  const [whatsappOpen, setWhatsappOpen] = useState(false);

  const highCount = group.items.filter(i => i.priority_label === "high").length;

  return (
    <>
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: idx * 0.06, duration: 0.35 }}
        className="card"
        style={{ marginBottom: "var(--space-4)", overflow: "hidden" }}
      >
        {/* Header */}
        <div
          onClick={() => setOpen(v => !v)}
          style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            cursor: "pointer", padding: 0, userSelect: "none"
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <div style={{ width: 44, height: 44, borderRadius: 12, background: "var(--primary-50)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--primary-600)", flexShrink: 0 }}>
              <Package size={20} />
            </div>
            <div>
              <div style={{ fontWeight: 700, fontSize: "var(--text-base)", color: "var(--text-main)" }}>
                {group.distributor_name}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 3 }}>
                <span style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>{group.items.length} items</span>
                {highCount > 0 && (
                  <span style={{ display: "flex", alignItems: "center", gap: 3, fontSize: "var(--text-xs)", color: "var(--danger-text)", fontWeight: 600 }}>
                    <AlertTriangle size={11} /> {highCount} urgent
                  </span>
                )}
              </div>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: "var(--text-sm)", fontWeight: 700, color: "var(--text-main)" }}>{fmtMoney(group.total_estimated_cost)}</div>
              <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>est. cost</div>
            </div>
            <motion.button
              whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
              onClick={e => { e.stopPropagation(); setWhatsappOpen(true); }}
              style={{
                display: "flex", alignItems: "center", gap: 6, padding: "7px 14px",
                background: "#25D366", color: "#fff", border: "none", borderRadius: "var(--radius-full)",
                fontSize: "var(--text-xs)", fontWeight: 700, cursor: "pointer"
              }}
            >
              <Send size={13} /> WhatsApp
            </motion.button>
            <div style={{ color: "var(--text-muted)", transition: "transform 0.2s", transform: open ? "rotate(180deg)" : "rotate(0deg)" }}>
              <ChevronDown size={18} />
            </div>
          </div>
        </div>

        {/* Items Table */}
        <AnimatePresence initial={false}>
          {open && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.25 }}
              style={{ overflow: "hidden" }}
            >
              <div className="table-container" style={{ marginTop: "var(--space-4)", borderRadius: "var(--radius-md)" }}>
                <table className="table">
                  <thead>
                    <tr>
                      <th>Medicine</th>
                      <th style={{ textAlign: "center" }}>Priority</th>
                      <th style={{ textAlign: "right" }}>Order Qty</th>
                      <th style={{ textAlign: "right" }}>14d Demand</th>
                      <th style={{ textAlign: "right" }}>Usable Stock</th>
                      <th style={{ textAlign: "right" }}>Last Rate</th>
                      <th style={{ textAlign: "right" }}>Est. Cost</th>
                      <th style={{ textAlign: "right" }}>Days Left</th>
                    </tr>
                  </thead>
                  <tbody>
                    {group.items.map((item, i) => (
                      <motion.tr
                        key={item.medicine_id}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: i * 0.03 }}
                      >
                        <td>
                          <div style={{ fontWeight: 600, fontSize: "var(--text-sm)" }}>{item.medicine_name}</div>
                          {item.unit && <div style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)" }}>{item.unit}</div>}
                          {item.near_expiry_qty > 0 && (
                            <div style={{ display: "flex", alignItems: "center", gap: 4, color: "var(--warning-text)", fontSize: "var(--text-xs)", marginTop: 2 }}>
                              <AlertTriangle size={10} /> {fmtQty(item.near_expiry_qty)} expiring soon (excluded)
                            </div>
                          )}
                        </td>
                        <td style={{ textAlign: "center" }}>
                          <PriorityBadge label={item.priority_label} />
                        </td>
                        <td style={{ textAlign: "right", fontWeight: 700, fontSize: "var(--text-base)", color: "var(--primary-600)" }}>
                          {fmtQty(item.order_qty)}
                        </td>
                        <td style={{ textAlign: "right", color: "var(--text-muted)", fontSize: "var(--text-sm)" }}>{fmtQty(item.demand_14d)}</td>
                        <td style={{ textAlign: "right", color: "var(--text-muted)", fontSize: "var(--text-sm)" }}>{fmtQty(item.usable_stock)}</td>
                        <td style={{ textAlign: "right", fontSize: "var(--text-sm)" }}>{fmtMoney(item.last_net_rate)}</td>
                        <td style={{ textAlign: "right", fontWeight: 600, fontSize: "var(--text-sm)", color: item.estimated_cost ? "var(--text-main)" : "var(--text-muted)" }}>
                          {fmtMoney(item.estimated_cost)}
                        </td>
                        <td style={{ textAlign: "right" }}>
                          {item.days_of_stock_remaining != null ? (
                            <span style={{
                              fontSize: "var(--text-xs)", fontWeight: 700,
                              color: item.days_of_stock_remaining <= 2 ? "var(--danger-text)" : item.days_of_stock_remaining <= 7 ? "var(--warning-text)" : "var(--success-text)"
                            }}>
                              {item.days_of_stock_remaining}d
                            </span>
                          ) : "—"}
                        </td>
                      </motion.tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      <AnimatePresence>
        {whatsappOpen && <WhatsAppModal group={group} onClose={() => setWhatsappOpen(false)} />}
      </AnimatePresence>
    </>
  );
}

/* ─── Main Page ─────────────────────────────────────────────────────────── */
export default function SmartPurchase() {
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastRefreshed, setLastRefreshed] = useState(null);

  const load = useCallback(() => {
    setLoading(true); setError("");
    api.getSmartPurchaseOrder()
      .then(d => { setOrder(d); setLastRefreshed(new Date()); })
      .catch(e => setError(e.message || "Failed to generate purchase order"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const totalCost = order?.groups?.reduce((s, g) => s + (g.total_estimated_cost || 0), 0) ?? 0;
  const totalItems = order?.items_count ?? 0;
  const highPri = order?.groups?.flatMap(g => g.items).filter(i => i.priority_label === "high").length ?? 0;

  return (
    <div style={{ padding: "var(--space-6) var(--space-8)" }}>
      {/* Page header */}
      <motion.div initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }} style={{ marginBottom: "var(--space-6)" }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 6 }}>
              <div style={{ width: 44, height: 44, borderRadius: 12, background: "linear-gradient(135deg, var(--primary-500), var(--primary-700))", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", boxShadow: "0 4px 12px rgba(20,184,166,0.3)" }}>
                <ShoppingBag size={22} />
              </div>
              <div>
                <h1 style={{ fontSize: "var(--text-2xl)", fontWeight: 800, letterSpacing: "-0.03em", marginBottom: 0, background: "linear-gradient(to right, var(--primary-700), var(--primary-500))", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
                  Smart Purchase AI
                </h1>
                <p style={{ color: "var(--text-muted)", fontSize: "var(--text-sm)", marginBottom: 0 }}>
                  AI-generated weekly purchase order — demand forecast + stock levels + lead times + near-expiry analysis
                </p>
              </div>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            {lastRefreshed && (
              <span style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
                Generated {lastRefreshed.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}
              </span>
            )}
            <motion.button
              whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.96 }}
              onClick={load}
              disabled={loading}
              className="btn btn-secondary"
              style={{ display: "flex", alignItems: "center", gap: 7, fontSize: "var(--text-sm)" }}
            >
              <RefreshCw size={14} className={loading ? "spin" : ""} />
              {loading ? "Generating…" : "Regenerate"}
            </motion.button>
          </div>
        </div>
      </motion.div>

      {/* How it works info banner */}
      <motion.div
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.1 }}
        style={{ background: "var(--info-bg)", border: "1px solid var(--info-border)", borderRadius: "var(--radius-md)", padding: "12px 16px", marginBottom: "var(--space-5)", display: "flex", alignItems: "flex-start", gap: 10 }}
      >
        <Info size={15} color="var(--info-text)" style={{ marginTop: 1, flexShrink: 0 }} />
        <p style={{ fontSize: "var(--text-xs)", color: "var(--info-text)", margin: 0, lineHeight: 1.6 }}>
          <strong>How quantities are calculated:</strong> 14-day demand forecast (Holt-Winters) minus usable stock (current stock minus near-expiry batches expiring within your lead time). Near-expiry quantities are automatically excluded to avoid over-ordering stock you'll discard. Grouped by last confirmed distributor.
        </p>
      </motion.div>

      {/* Stat cards */}
      {!loading && !error && order && (
        <div style={{ display: "flex", gap: "var(--space-4)", marginBottom: "var(--space-6)", flexWrap: "wrap" }}>
          <StatCard icon={<Package size={18} />} label="Items to Order" value={totalItems} sub={`across ${order.groups?.length || 0} distributors`} />
          <StatCard icon={<DollarSign size={18} />} label="Total Est. Cost" value={fmtMoney(totalCost)} sub="based on last purchase rates" color="var(--accent-600)" />
          <StatCard icon={<AlertTriangle size={18} />} label="Urgent Items" value={highPri} sub="depleting within lead time" color="var(--danger-text)" />
          <StatCard icon={<Clock size={18} />} label="Order By" value="Monday 9am" sub="Celery Beat auto-refreshes weekly" color="var(--primary-700)" />
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
          {[1, 2, 3].map(i => (
            <div key={i} className="card">
              <div className="skeleton" style={{ height: 60, borderRadius: "var(--radius-md)" }} />
            </div>
          ))}
          <div style={{ textAlign: "center", color: "var(--text-muted)", fontSize: "var(--text-sm)", marginTop: 8 }}>
            <Loader2 size={16} className="spin" style={{ display: "inline", marginRight: 6 }} />
            Analysing demand forecasts, stock levels &amp; lead times…
          </div>
        </div>
      )}

      {/* Error */}
      {!loading && error && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="card" style={{ background: "var(--danger-bg)", border: "1px solid var(--danger-border)", color: "var(--danger-text)", textAlign: "center", padding: "var(--space-8)" }}>
          <AlertTriangle size={32} style={{ margin: "0 auto 12px" }} />
          <p style={{ fontWeight: 600, marginBottom: 8 }}>{error}</p>
          <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} className="btn btn-primary" onClick={load}>Try Again</motion.button>
        </motion.div>
      )}

      {/* Empty state */}
      {!loading && !error && (!order?.groups || order.groups.length === 0) && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="card" style={{ textAlign: "center", padding: "var(--space-12)" }}>
          <CheckCircle size={48} color="var(--success-text)" style={{ margin: "0 auto 16px" }} />
          <h3 style={{ marginBottom: 8 }}>You're all set! 🎉</h3>
          <p style={{ color: "var(--text-muted)", fontSize: "var(--text-sm)" }}>
            No medicines need reordering this week based on the 14-day demand forecast and current stock levels.
          </p>
        </motion.div>
      )}

      {/* Purchase order groups */}
      {!loading && !error && order?.groups?.map((group, idx) => (
        <DistributorGroup key={group.distributor_name} group={group} idx={idx} />
      ))}

      {/* Footer note */}
      {!loading && !error && order && (
        <motion.p
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.4 }}
          style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)", textAlign: "center", marginTop: "var(--space-6)", lineHeight: 1.8 }}
        >
          Generated {order.generated_at ? new Date(order.generated_at).toLocaleString("en-IN") : "just now"} · 
          Quantities use 14-day Holt-Winters forecast · Near-expiry stock automatically excluded ·
          Celery Beat regenerates every Monday 7am IST
        </motion.p>
      )}

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        .spin { animation: spin 1s linear infinite; }
      `}</style>
    </div>
  );
}
