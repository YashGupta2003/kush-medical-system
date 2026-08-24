import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { CheckCircle, Package, AlertTriangle, Building, Search, Plus, Edit3, ClipboardList, Lightbulb, TrendingUp } from "lucide-react";
import { api, getToken } from "../api/client.js";
import MagneticButton from "../components/MagneticButton.jsx";
import TableSkeleton from "../components/TableSkeleton.jsx";
import ConfettiExplosion from "../components/ConfettiExplosion.jsx";

// ---------------------------------------------------------------------------
// TAB 1: Record a Sale
// ---------------------------------------------------------------------------
function RecordSaleTab() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [selected, setSelected] = useState(null);
  const [snapshot, setSnapshot] = useState(null);
  const [qtySold, setQtySold] = useState("");
  const [saving, setSaving] = useState(false);
  const [confirmation, setConfirmation] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (query.length < 2) { setResults([]); return; }
    const t = setTimeout(() => {
      api.browseMedicines({ q: query, page: 1, page_size: 10 }).then((d) => setResults(d.items));
    }, 250);
    return () => clearTimeout(t);
  }, [query]);

  async function selectMedicine(med) {
    setSelected(med);
    setConfirmation(null);
    setError(null);
    setResults([]);
    setQuery(med.particulars);
    try {
      const snap = await api.getStockSnapshot(med.id);
      setSnapshot(snap);
    } catch {
      setSnapshot({
        medicine_id: med.id,
        medicine_name: med.particulars,
        current_stock: med.current_stock ?? 0,
        low_stock_threshold: med.low_stock_threshold,
      });
    }
  }

  async function handleRecordSale(e) {
    e.preventDefault();
    if (!selected || !qtySold) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await api.recordSale(selected.id, Number(qtySold));
      setSnapshot(updated);
      setConfirmation(`Recorded: ${qtySold} sold. Stock is now ${updated.current_stock}.`);
      setQtySold("");
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
      <div className="card">
        <h2 style={{ color: "var(--text-main)", marginTop: 0 }}>Record a Sale</h2>
        <p style={{ color: "var(--text-secondary)", fontSize: "13px", lineHeight: 1.5 }}>
          Search the medicine that was just sold, check current stock levels, then enter how many pieces were sold.
        </p>
        <div style={{ position: "relative" }}>
          <Search size={16} style={{ position: "absolute", left: "12px", top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }} />
          <input
            style={{ width: "100%", paddingLeft: "36px" }}
            placeholder="Search medicine name (e.g. AMLOKIND-AT TABS)..."
            value={query}
            onChange={(e) => { setQuery(e.target.value); setSelected(null); setSnapshot(null); }}
          />
        </div>
        {results.length > 0 && (
          <div style={{ marginTop: "12px", border: "1px solid var(--border-color)", borderRadius: "8px", overflow: "hidden" }}>
            <table className="table" style={{ width: "100%", margin: 0 }}>
              <tbody>
                {results.map((m) => (
                  <tr key={m.id} onClick={() => selectMedicine(m)} style={{ cursor: "pointer", transition: "background 0.2s" }} className="hover-row">
                    <td style={{ padding: "10px", borderBottom: "1px solid var(--border-color)" }}><strong style={{ color: "var(--text-main)" }}>{m.particulars}</strong></td>
                    <td style={{ padding: "10px", color: "var(--text-muted)", borderBottom: "1px solid var(--border-color)" }}>{m.unit || "—"}</td>
                    <td style={{ padding: "10px", borderBottom: "1px solid var(--border-color)", textAlign: "right" }}>Stock: {m.current_stock ?? 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {snapshot && (
        <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} className="card" style={{ marginTop: "16px" }}>
          <h3 style={{ marginTop: 0, color: "var(--text-main)" }}>{snapshot.medicine_name}</h3>

          <div className="stat-row">
            <div className={`stat-box ${snapshot.low_stock_threshold != null && snapshot.current_stock < snapshot.low_stock_threshold ? "warn" : ""}`}>
              <div className="value">{snapshot.current_stock}</div>
              <div className="label">Current stock</div>
            </div>
            <div className="stat-box">
              <div className="value">{snapshot.low_stock_threshold ?? "—"}</div>
              <div className="label">Low-stock alert below</div>
            </div>
          </div>

          {snapshot.last_purchase ? (
            <div className="last-purchase-card" style={{ background: "var(--bg-muted)", padding: "16px", borderRadius: "8px", marginTop: "16px" }}>
              <div className="title" style={{ display: "flex", alignItems: "center", gap: "6px", fontWeight: 600, color: "var(--text-main)", marginBottom: "8px" }}>
                <Package size={16} /> Last Delivery Received
              </div>
              <div style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "4px" }}>
                <strong style={{ color: "var(--text-main)" }}>{snapshot.last_purchase.qty_received}</strong> units
                {snapshot.last_purchase.free_qty_received > 0 && <> (+{snapshot.last_purchase.free_qty_received} free)</>}
                {" "}from <strong style={{ color: "var(--text-main)" }}>{snapshot.last_purchase.distributor_name || "distributor"}</strong>
              </div>
              <div style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "4px" }}>Rate: ₹{snapshot.last_purchase.rate ?? "—"} · MRP: ₹{snapshot.last_purchase.mrp ?? "—"}</div>
              <div style={{ fontSize: "13px", color: "var(--text-secondary)" }}>Date: {snapshot.last_purchase.purchase_date ? new Date(snapshot.last_purchase.purchase_date).toLocaleDateString() : "—"}</div>
            </div>
          ) : (
            <p style={{ color: "var(--text-muted)", fontSize: "13px", marginTop: "16px" }}>No purchase history found yet for this medicine.</p>
          )}

          <form onSubmit={handleRecordSale} style={{ display: "flex", gap: "12px", alignItems: "flex-end", marginTop: "20px", position: "relative" }}>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "4px", display: "block" }}>Quantity Sold</label>
              <input
                type="number" min="0.01" step="0.01" required
                style={{ width: "100%" }}
                value={qtySold}
                onChange={(e) => setQtySold(e.target.value)}
              />
            </div>
            <MagneticButton type="submit" disabled={saving}>
              {saving ? "Saving..." : "Record sale"}
            </MagneticButton>
            <ConfettiExplosion show={!!confirmation} onComplete={() => {}} />
          </form>

          {confirmation && <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "var(--success-600)", background: "var(--success-100)", padding: "10px", borderRadius: "8px", marginTop: "16px", fontSize: "14px" }}><CheckCircle size={18} /> {confirmation}</div>}
          {error && <p style={{ color: "var(--danger-600)", marginTop: "16px", fontSize: "14px" }}>{error}</p>}
        </motion.div>
      )}
      <style>{`.hover-row:hover { background: var(--bg-muted) !important; }`}</style>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// TAB 2: Manual Stock Adjustment
// ---------------------------------------------------------------------------
function AdjustmentTab() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [selected, setSelected] = useState(null);
  const [newStock, setNewStock] = useState("");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (query.length < 2) { setResults([]); return; }
    const t = setTimeout(() => {
      api.browseMedicines({ q: query, page: 1, page_size: 10 }).then((d) => setResults(d.items));
    }, 250);
    return () => clearTimeout(t);
  }, [query]);

  async function handleAdjust(e) {
    e.preventDefault();
    if (!selected || newStock === "") return;
    setSaving(true);
    setError(null);
    try {
      const res = await api.recordAdjustment({
        medicine_id: selected.id,
        new_total_stock: Number(newStock),
        note: note.trim() || undefined,
      });
      setMessage(`Stock updated for ${selected.particulars}. New total balance: ${res.resulting_balance}`);
      setSelected(null);
      setNewStock("");
      setNote("");
      setQuery("");
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }} className="card">
      <h2 style={{ color: "var(--text-main)", marginTop: 0 }}>Manual Physical Inventory Adjustment</h2>
      <p style={{ color: "var(--text-secondary)", fontSize: "13px", lineHeight: 1.5 }}>
        Directly align stock records with physical shelf counts (e.g. damaged stock, manual audit counts). Every change is audited in the Stock Ledger.
      </p>
      <form onSubmit={handleAdjust}>
        <div style={{ marginBottom: "16px" }}>
          <label style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "4px", display: "block" }}>Select Medicine</label>
          <div style={{ position: "relative" }}>
            <Search size={16} style={{ position: "absolute", left: "12px", top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }} />
            <input
              style={{ width: "100%", paddingLeft: "36px" }}
              placeholder="Search medicine to adjust..."
              value={selected ? selected.particulars : query}
              onChange={(e) => { setQuery(e.target.value); setSelected(null); }}
            />
          </div>
          {results.length > 0 && !selected && (
            <div style={{ marginTop: "8px", border: "1px solid var(--border-color)", borderRadius: "8px", overflow: "hidden" }}>
              <table className="table" style={{ width: "100%", margin: 0 }}>
                <tbody>
                  {results.map((m) => (
                    <tr key={m.id} style={{ cursor: "pointer" }} onClick={() => { setSelected(m); setNewStock(m.current_stock ?? 0); setResults([]); }} className="hover-row">
                      <td style={{ padding: "10px", borderBottom: "1px solid var(--border-color)" }}><strong style={{ color: "var(--text-main)" }}>{m.particulars}</strong></td>
                      <td style={{ padding: "10px", borderBottom: "1px solid var(--border-color)", textAlign: "right" }}>Current: {m.current_stock ?? 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {selected && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }}>
            <div style={{ display: "flex", gap: "16px", marginBottom: "16px", flexWrap: "wrap" }}>
              <div style={{ flex: 1, minWidth: "150px" }}>
                <label style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "4px", display: "block" }}>New Physical Stock Count</label>
                <input
                  type="number" step="0.01" required
                  style={{ width: "100%" }}
                  value={newStock}
                  onChange={(e) => setNewStock(e.target.value)}
                />
              </div>
              <div style={{ flex: 2, minWidth: "200px" }}>
                <label style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "4px", display: "block" }}>Audit Note / Reason</label>
                <input
                  placeholder="e.g. Shelf audit, broken bottle discarded"
                  style={{ width: "100%" }}
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                />
              </div>
            </div>
            <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? "Saving..." : "Save Adjustment"}</button>
          </motion.div>
        )}
      </form>
      {message && <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "var(--success-600)", background: "var(--success-100)", padding: "10px", borderRadius: "8px", marginTop: "16px", fontSize: "14px" }}><CheckCircle size={18} /> {message}</div>}
      {error && <p style={{ color: "var(--danger-600)", marginTop: "16px", fontSize: "14px" }}>{error}</p>}
      <style>{`.hover-row:hover { background: var(--bg-muted) !important; }`}</style>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// TAB 3: Stock Ledger Audit Trail
// ---------------------------------------------------------------------------
function StockLedgerTab() {
  const [ledger, setLedger] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getAuditLedger({ limit: 50 })
      .then((res) => setLedger(res.items || res))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }} className="card">
      <h2 style={{ color: "var(--text-main)", marginTop: 0 }}>Stock Ledger Audit Trail</h2>
      <p style={{ color: "var(--text-secondary)", fontSize: "13px", lineHeight: 1.5 }}>
        Immutable history of every inventory change across bills, sales, and adjustments.
      </p>
      {loading ? (
        <TableSkeleton rows={8} columns={6} />
      ) : ledger.length === 0 ? (
        <p style={{ color: "var(--text-muted)", padding: "20px", textAlign: "center" }}>No ledger movements recorded yet.</p>
      ) : (
        <div style={{ overflowX: "auto", marginTop: "16px", border: "1px solid var(--border-color)", borderRadius: "8px" }}>
          <table className="table" style={{ width: "100%", margin: 0 }}>
            <thead style={{ background: "var(--bg-muted)" }}>
              <tr>
                <th style={{ padding: "12px", textAlign: "left" }}>Timestamp</th>
                <th style={{ padding: "12px", textAlign: "left" }}>Medicine</th>
                <th style={{ padding: "12px", textAlign: "left" }}>Reason</th>
                <th style={{ padding: "12px", textAlign: "right" }}>Change Qty</th>
                <th style={{ padding: "12px", textAlign: "right" }}>Resulting Balance</th>
                <th style={{ padding: "12px", textAlign: "left" }}>Note / Ref</th>
              </tr>
            </thead>
            <tbody>
              {ledger.map((row) => (
                <tr key={row.id} style={{ transition: "background 0.2s" }} className="hover-row">
                  <td style={{ padding: "12px", borderBottom: "1px solid var(--border-color)", whiteSpace: "nowrap", color: "var(--text-secondary)" }}>{new Date(row.created_at).toLocaleString()}</td>
                  <td style={{ padding: "12px", borderBottom: "1px solid var(--border-color)" }}><strong style={{ color: "var(--text-main)" }}>{row.medicine_name || row.medicine_id}</strong></td>
                  <td style={{ padding: "12px", borderBottom: "1px solid var(--border-color)" }}>
                    <span className={`badge ${row.reason === "bill_received" ? "auto" : row.reason === "sale" ? "learned" : "manual"}`}>
                      {row.reason}
                    </span>
                  </td>
                  <td style={{ padding: "12px", borderBottom: "1px solid var(--border-color)", textAlign: "right", color: row.change_qty > 0 ? "var(--success-600)" : "var(--danger-600)", fontWeight: "bold" }}>
                    {row.change_qty > 0 ? `+${row.change_qty}` : row.change_qty}
                  </td>
                  <td style={{ padding: "12px", borderBottom: "1px solid var(--border-color)", textAlign: "right" }}><strong style={{ color: "var(--text-main)" }}>{row.resulting_balance}</strong></td>
                  <td style={{ padding: "12px", borderBottom: "1px solid var(--border-color)", color: "var(--text-secondary)", fontSize: "13px" }}>{row.note || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <style>{`.hover-row:hover { background: var(--bg-muted) !important; }`}</style>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Add-manual-item modal for Reorder
// ---------------------------------------------------------------------------
function AddReorderItemModal({ onClose, onAdded }) {
  const [mode, setMode] = useState("existing");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [selectedMedicine, setSelectedMedicine] = useState(null);
  const [customName, setCustomName] = useState("");
  const [distributorName, setDistributorName] = useState("");
  const [quantity, setQuantity] = useState("");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (mode !== "existing" || query.length < 2) { setResults([]); return; }
    const t = setTimeout(() => {
      api.browseMedicines({ q: query, page: 1, page_size: 8 }).then((d) => setResults(d.items));
    }, 250);
    return () => clearTimeout(t);
  }, [query, mode]);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    if (mode === "existing" && !selectedMedicine) {
      setError("Please select a medicine from the search results, or switch to 'New item'.");
      return;
    }
    if (mode === "custom" && !customName.trim()) {
      setError("Please type the item's name.");
      return;
    }
    setSaving(true);
    try {
      await api.addManualReorderItem({
        medicine_id: mode === "existing" ? selectedMedicine.id : null,
        custom_name: mode === "custom" ? customName.trim() : null,
        distributor_name_new: distributorName.trim() || null,
        quantity_needed: quantity ? Number(quantity) : null,
        note: note.trim() || null,
      });
      onAdded();
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose} style={{ zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(0,0,0,0.4)" }}>
      <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="modal-box" onClick={(e) => e.stopPropagation()} style={{ width: "100%", maxWidth: "500px" }}>
        <h3 style={{ marginTop: 0, color: "var(--text-main)" }}>Add item to reorder list</h3>
        <div className="tabs" style={{ marginBottom: "16px" }}>
          <button className={`tab-button ${mode === "existing" ? "active" : ""}`} onClick={() => setMode("existing")}>Existing medicine</button>
          <button className={`tab-button ${mode === "custom" ? "active" : ""}`} onClick={() => setMode("custom")}>New item</button>
        </div>

        <form onSubmit={handleSubmit}>
          {mode === "existing" ? (
            <div style={{ marginBottom: "16px" }}>
              <label style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "4px", display: "block" }}>Search medicine</label>
              <div style={{ position: "relative" }}>
                <Search size={16} style={{ position: "absolute", left: "12px", top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }} />
                <input
                  style={{ width: "100%", paddingLeft: "36px" }}
                  value={selectedMedicine ? selectedMedicine.particulars : query}
                  onChange={(e) => { setQuery(e.target.value); setSelectedMedicine(null); }}
                  placeholder="Start typing..."
                />
              </div>
              {results.length > 0 && !selectedMedicine && (
                <div style={{ marginTop: "8px", border: "1px solid var(--border-color)", borderRadius: "8px", overflow: "hidden" }}>
                  <table className="table" style={{ width: "100%", margin: 0 }}>
                    <tbody>
                      {results.map((m) => (
                        <tr key={m.id} style={{ cursor: "pointer" }} onClick={() => { setSelectedMedicine(m); setResults([]); }} className="hover-row">
                          <td style={{ padding: "10px", borderBottom: "1px solid var(--border-color)" }}>{m.particulars}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ) : (
            <div style={{ marginBottom: "16px" }}>
              <label style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "4px", display: "block" }}>Item name</label>
              <input style={{ width: "100%" }} value={customName} onChange={(e) => setCustomName(e.target.value)}
                placeholder="e.g. Listerine Mouthwash 250ml" />
            </div>
          )}

          <div style={{ marginBottom: "16px" }}>
            <label style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "4px", display: "block" }}>Order from distributor (optional)</label>
            <input style={{ width: "100%" }} value={distributorName} onChange={(e) => setDistributorName(e.target.value)}
              placeholder="e.g. RATHORE MEDICOS" />
          </div>

          <div style={{ display: "flex", gap: "12px", marginBottom: "16px" }}>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "4px", display: "block" }}>Quantity needed</label>
              <input type="number" min="1" style={{ width: "100%" }} value={quantity} onChange={(e) => setQuantity(e.target.value)} />
            </div>
          </div>

          <div style={{ marginBottom: "20px" }}>
            <label style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "4px", display: "block" }}>Note (optional)</label>
            <input style={{ width: "100%" }} value={note} onChange={(e) => setNote(e.target.value)} />
          </div>

          {error && <p style={{ color: "var(--danger-600)", fontSize: "13px", marginBottom: "16px" }}>{error}</p>}

          <div style={{ display: "flex", gap: "12px", justifyContent: "flex-end" }}>
            <button type="button" className="btn secondary" onClick={onClose}>Cancel</button>
            <MagneticButton type="submit" disabled={saving}>{saving ? "Adding..." : "Add to list"}</MagneticButton>
          </div>
        </form>
      </motion.div>
      <style>{`.hover-row:hover { background: var(--bg-muted) !important; }`}</style>
    </div>
  );
}

// ---------------------------------------------------------------------------
// TAB 4: Reorder List (grouped by distributor)
// ---------------------------------------------------------------------------
function ReorderListTab() {
  const [groups, setGroups] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [loading, setLoading] = useState(true);

  function refresh() {
    api.getReorderList().then((g) => { setGroups(g); setLoading(false); });
  }

  useEffect(() => { refresh(); }, []);

  async function handleFulfill(id) {
    await api.fulfillReorderItem(id);
    refresh();
  }

  async function handleRemove(id) {
    await api.removeReorderItem(id);
    refresh();
  }

  const totalItems = groups.reduce((sum, g) => sum + g.items.length, 0);

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
      <div className="card" style={{ marginBottom: "20px" }}>
        <div className="flex-between">
          <div>
            <h2 style={{ marginBottom: "8px", color: "var(--text-main)", marginTop: 0 }}>Reorder List</h2>
            <p style={{ color: "var(--text-secondary)", fontSize: "13px", margin: 0 }}>
              Grouped by distributor, so you know exactly who to call and what to ask for.
              {totalItems > 0 && <> <strong style={{ color: "var(--text-main)" }}>{totalItems}</strong> item{totalItems === 1 ? "" : "s"} need attention.</>}
            </p>
          </div>
          <button className="btn btn-primary" onClick={() => setShowModal(true)} style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <Plus size={16} /> Add manual item
          </button>
        </div>
      </div>

      {loading && <TableSkeleton rows={4} columns={4} />}
      {!loading && groups.length === 0 && (
        <div className="card" style={{ textAlign: "center", padding: "40px 20px" }}>
          <p style={{ color: "var(--text-secondary)", fontSize: "15px" }}>Nothing to reorder right now — stock levels look healthy.</p>
        </div>
      )}

      {groups.map((group) => {
        const isFallback = group.distributor_name.includes("Unknown") || group.distributor_name.includes("Unassigned");
        return (
          <div className="distributor-group" key={group.distributor_name} style={{ background: "var(--bg-surface)", border: "1px solid var(--border-color)", borderRadius: "12px", marginBottom: "20px", overflow: "hidden" }}>
            <div className={`distributor-group-header ${isFallback ? "fallback" : ""}`} style={{ background: isFallback ? "var(--warning-100)" : "var(--bg-muted)", padding: "12px 16px", borderBottom: "1px solid var(--border-color)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span className="name" style={{ display: "flex", alignItems: "center", gap: "8px", fontWeight: 600, color: isFallback ? "var(--warning-800)" : "var(--text-main)" }}>
                {isFallback ? <AlertTriangle size={18} /> : <Building size={18} />} {group.distributor_name}
              </span>
              <span className="count" style={{ background: "var(--bg-surface)", padding: "2px 8px", borderRadius: "12px", fontSize: "12px", color: "var(--text-secondary)", fontWeight: 600 }}>{group.items.length} item{group.items.length === 1 ? "" : "s"}</span>
            </div>
            {group.items.map((item, idx) => (
              <div className="reorder-item-row" key={item.id ?? `auto-${item.medicine_id}-${idx}`} style={{ padding: "16px", borderBottom: idx < group.items.length - 1 ? "1px solid var(--border-color)" : "none", display: "flex", justifyContent: "space-between", alignItems: "center", gap: "16px", flexWrap: "wrap" }}>
                <div style={{ flex: 1, minWidth: "250px" }}>
                  <div className="reorder-item-name" style={{ fontWeight: 600, color: "var(--text-main)", fontSize: "15px", marginBottom: "4px" }}>{item.name}</div>
                  <div className="reorder-item-meta" style={{ fontSize: "13px", color: "var(--text-secondary)", lineHeight: 1.5 }}>
                    {item.current_stock != null && <>Stock: <strong style={{ color: "var(--text-main)" }}>{item.current_stock}</strong>{item.low_stock_threshold != null && <> (below {item.low_stock_threshold})</>} · </>}
                    {item.last_qty_received != null && <>Last order: {item.last_qty_received} units @ ₹{item.last_rate ?? "—"} </>}
                    {item.last_purchase_date && <>on {new Date(item.last_purchase_date).toLocaleDateString()} </>}
                    {item.quantity_needed != null && <>· <strong style={{ color: "var(--primary-600)" }}>Need: {item.quantity_needed}</strong></>}
                    {item.note && <div style={{ marginTop: "4px", fontStyle: "italic" }}>"{item.note}"</div>}
                  </div>
                </div>
                <div className="reorder-item-actions" style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                  <span className={`badge ${item.source === "auto_low_stock" ? "unmatched" : "manual"}`} style={{ whiteSpace: "nowrap" }}>
                    {item.source === "auto_low_stock" ? "Low stock" : "Manually added"}
                  </span>
                  {item.id && (
                    <div style={{ display: "flex", gap: "8px" }}>
                      <button className="btn btn-primary" onClick={() => handleFulfill(item.id)} style={{ padding: "6px 12px", fontSize: "13px" }}>Mark Fulfilled</button>
                      <button className="btn secondary" onClick={() => handleRemove(item.id)} style={{ padding: "6px 12px", fontSize: "13px" }}>Remove</button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        );
      })}

      {showModal && <AddReorderItemModal onClose={() => setShowModal(false)} onAdded={refresh} />}
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// ---------------------------------------------------------------------------
// TAB 5: Smart Reorder Engine
// ---------------------------------------------------------------------------
function SmartReorderTab() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [windowDays, setWindowDays] = useState(30);
  const [notice, setNotice] = useState(null);
  const [error, setError] = useState(null);

  function loadList() {
    setLoading(true);
    setError(null);
    fetch(`/api/stock/smart-reorder?window_days=${windowDays}`, {
      headers: { "Authorization": `Bearer ${getToken()}` }
    })
      .then((r) => r.ok ? r.json() : r.json().then(e => Promise.reject(e)))
      .then((data) => setItems(data))
      .catch((err) => setError(err.message || err.detail || "Failed to load smart reorder list"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    loadList();
  }, [windowDays]);

  async function handleApply(medicineId) {
    setNotice(null);
    setError(null);
    try {
      const res = await fetch(`/api/stock/medicine/${medicineId}/smart-threshold/apply`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${getToken()}` }
      });
      if (!res.ok) {
        const e = await res.json();
        throw new Error(e.detail || "Failed to apply smart threshold");
      }
      const updated = await res.json();
      setNotice(`Applied smart threshold ${updated.low_stock_threshold} for medicine ID ${medicineId}.`);
      loadList();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleLeadTimeChange(medicineId, val) {
    const parsed = val === "" ? null : parseInt(val, 10);
    try {
      const res = await fetch(`/api/stock/medicine/${medicineId}/lead-time`, {
        method: "PATCH",
        headers: { "Authorization": `Bearer ${getToken()}`, "Content-Type": "application/json" },
        body: JSON.stringify({ lead_time_days: parsed })
      });
      if (!res.ok) {
        const e = await res.json();
        throw new Error(e.detail || "Failed to update lead time");
      }
      loadList();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
      <div className="card">
        <div className="flex-between" style={{ flexWrap: "wrap", gap: "16px" }}>
          <div>
            <h2 style={{ marginBottom: "8px", color: "var(--text-main)", marginTop: 0 }}>Smart Reorder Point Engine</h2>
            <p style={{ color: "var(--text-secondary)", fontSize: "13px", margin: 0, lineHeight: 1.5 }}>
              Data-driven reorder point suggestions based on rolling sales history, lead time demand, and safety stock.
            </p>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "12px", background: "var(--bg-muted)", padding: "8px 16px", borderRadius: "8px" }}>
            <label style={{ fontSize: "13px", color: "var(--text-secondary)", fontWeight: 500 }}>Rolling Window:</label>
            <select style={{ border: "1px solid var(--border-color)", borderRadius: "6px", padding: "4px 8px" }} value={windowDays} onChange={(e) => setWindowDays(Number(e.target.value))}>
              <option value={7}>7 Days</option>
              <option value={14}>14 Days</option>
              <option value={30}>30 Days</option>
              <option value={60}>60 Days</option>
              <option value={90}>90 Days</option>
            </select>
          </div>
        </div>
        {notice && <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "var(--success-600)", background: "var(--success-100)", padding: "10px", borderRadius: "8px", marginTop: "16px", fontSize: "14px" }}><CheckCircle size={18} /> {notice}</div>}
        {error && <p style={{ color: "var(--danger-600)", marginTop: "16px", fontSize: "14px" }}>{error}</p>}
      </div>

      {loading ? (
        <TableSkeleton rows={6} columns={6} />
      ) : items.length === 0 ? (
        <div className="card" style={{ textAlign: "center", padding: "40px 20px" }}><p style={{ color: "var(--text-secondary)", fontSize: "15px" }}>No sales history recorded yet across medicines.</p></div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ overflowX: "auto" }}>
            <table className="table" style={{ width: "100%", margin: 0 }}>
              <thead style={{ background: "var(--bg-muted)" }}>
                <tr>
                  <th style={{ padding: "12px", textAlign: "left" }}>Medicine</th>
                  <th style={{ padding: "12px", textAlign: "right" }}>Avg. Daily Sales ({windowDays}d)</th>
                  <th style={{ padding: "12px", textAlign: "right" }}>Current Threshold</th>
                  <th style={{ padding: "12px", textAlign: "right" }}>Suggested Threshold</th>
                  <th style={{ padding: "12px", textAlign: "center" }}>Lead Time (Days)</th>
                  <th style={{ padding: "12px", textAlign: "right" }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {items.map((row) => (
                  <tr key={row.medicine_id} style={{ opacity: row.has_sufficient_data ? 1 : 0.65, transition: "background 0.2s" }} className="hover-row">
                    <td style={{ padding: "12px", borderBottom: "1px solid var(--border-color)" }}><strong style={{ color: "var(--text-main)" }}>{row.medicine_name || `Medicine #${row.medicine_id}`}</strong></td>
                    <td style={{ padding: "12px", borderBottom: "1px solid var(--border-color)", textAlign: "right", color: "var(--text-secondary)" }}>{row.avg_daily_sales} units/day</td>
                    <td style={{ padding: "12px", borderBottom: "1px solid var(--border-color)", textAlign: "right", color: "var(--text-muted)" }}>{row.current_threshold ?? "—"}</td>
                    <td style={{ padding: "12px", borderBottom: "1px solid var(--border-color)", textAlign: "right" }}>
                      {row.has_sufficient_data ? (
                        <strong style={{ color: "var(--primary-600)", fontSize: "15px", display: "flex", alignItems: "center", justifyContent: "flex-end", gap: "4px" }}>
                          <Lightbulb size={16} /> {row.suggested_threshold} units
                        </strong>
                      ) : (
                        <span style={{ color: "var(--text-muted)", fontSize: "12px", fontStyle: "italic" }}>
                          {row.reason || "Not enough sales data"}
                        </span>
                      )}
                    </td>
                    <td style={{ padding: "12px", borderBottom: "1px solid var(--border-color)", textAlign: "center" }}>
                      <input
                        type="number"
                        min="1"
                        style={{ width: "70px", padding: "4px 8px", textAlign: "center", border: "1px solid var(--border-color)", borderRadius: "4px" }}
                        defaultValue={row.lead_time_days}
                        onBlur={(e) => handleLeadTimeChange(row.medicine_id, e.target.value)}
                      />
                    </td>
                    <td style={{ padding: "12px", borderBottom: "1px solid var(--border-color)", textAlign: "right" }}>
                      <button
                        className={`btn ${row.has_sufficient_data ? "btn-primary" : "secondary"}`}
                        disabled={!row.has_sufficient_data}
                        onClick={() => handleApply(row.medicine_id)}
                        style={{ padding: "6px 12px", fontSize: "13px" }}
                      >
                        Apply suggestion
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      <style>{`.hover-row:hover { background: var(--bg-muted) !important; }`}</style>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Main Stock Component with Tabs
// ---------------------------------------------------------------------------
// TAB X: Add New Medicine
// ---------------------------------------------------------------------------
function AddMedicineTab() {
  const [formData, setFormData] = useState({
    particulars: "",
    unit: "",
    mrp: "",
    net_rate: "",
    company: "",
    stockist: "",
    current_stock: "",
    low_stock_threshold: "",
    composition: "",
  });
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const payload = {
        particulars: formData.particulars.trim(),
        unit: formData.unit.trim() || undefined,
        mrp: formData.mrp ? Number(formData.mrp) : undefined,
        net_rate: formData.net_rate ? Number(formData.net_rate) : undefined,
        company: formData.company.trim() || undefined,
        stockist: formData.stockist.trim() || undefined,
        current_stock: formData.current_stock ? Number(formData.current_stock) : 0,
        low_stock_threshold: formData.low_stock_threshold ? Number(formData.low_stock_threshold) : undefined,
        composition: formData.composition.trim() || undefined,
      };
      const res = await api.createMedicine(payload);
      setMessage(`Medicine "${res.particulars}" added successfully with initial stock ${res.current_stock || 0}.`);
      setFormData({
        particulars: "", unit: "", mrp: "", net_rate: "", company: "",
        stockist: "", current_stock: "", low_stock_threshold: "", composition: ""
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }} className="card">
      <h2 style={{ color: "var(--text-main)", marginTop: 0 }}>Add New Medicine to Inventory</h2>
      <p style={{ color: "var(--text-secondary)", fontSize: "13px", lineHeight: 1.5 }}>
        Manually add a new medicine to the system along with its initial stock. Usually, medicines are added automatically when uploading a purchase bill, but this allows for manual entry.
      </p>
      <form onSubmit={handleSubmit} style={{ display: "grid", gap: "16px", gridTemplateColumns: "1fr 1fr" }}>
        <div style={{ gridColumn: "1 / -1" }}>
          <label style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "4px", display: "block" }}>Medicine Name (Particulars) *</label>
          <input required style={{ width: "100%" }} value={formData.particulars} onChange={(e) => setFormData({...formData, particulars: e.target.value})} placeholder="e.g. PARACETAMOL 500MG TABS" />
        </div>
        
        <div>
          <label style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "4px", display: "block" }}>Composition (Salt)</label>
          <input style={{ width: "100%" }} value={formData.composition} onChange={(e) => setFormData({...formData, composition: e.target.value})} placeholder="e.g. Paracetamol" />
        </div>
        
        <div>
          <label style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "4px", display: "block" }}>Unit / Pack Size</label>
          <input style={{ width: "100%" }} value={formData.unit} onChange={(e) => setFormData({...formData, unit: e.target.value})} placeholder="e.g. 1x10" />
        </div>

        <div>
          <label style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "4px", display: "block" }}>MRP (₹)</label>
          <input type="number" step="0.01" style={{ width: "100%" }} value={formData.mrp} onChange={(e) => setFormData({...formData, mrp: e.target.value})} />
        </div>
        
        <div>
          <label style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "4px", display: "block" }}>Net Rate (Cost Price ₹)</label>
          <input type="number" step="0.01" style={{ width: "100%" }} value={formData.net_rate} onChange={(e) => setFormData({...formData, net_rate: e.target.value})} />
        </div>

        <div>
          <label style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "4px", display: "block" }}>Company / Manufacturer</label>
          <input style={{ width: "100%" }} value={formData.company} onChange={(e) => setFormData({...formData, company: e.target.value})} />
        </div>

        <div>
          <label style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "4px", display: "block" }}>Stockist</label>
          <input style={{ width: "100%" }} value={formData.stockist} onChange={(e) => setFormData({...formData, stockist: e.target.value})} />
        </div>

        <div>
          <label style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "4px", display: "block" }}>Initial Physical Stock (Quantity)</label>
          <input type="number" step="0.01" style={{ width: "100%" }} value={formData.current_stock} onChange={(e) => setFormData({...formData, current_stock: e.target.value})} placeholder="0" />
        </div>

        <div>
          <label style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "4px", display: "block" }}>Low Stock Alert Threshold</label>
          <input type="number" step="0.01" style={{ width: "100%" }} value={formData.low_stock_threshold} onChange={(e) => setFormData({...formData, low_stock_threshold: e.target.value})} />
        </div>

        <div style={{ gridColumn: "1 / -1", marginTop: "8px" }}>
          <button type="submit" className="button button-primary" disabled={saving}>
            {saving ? "Saving..." : "Add Medicine & Stock"}
          </button>
        </div>
      </form>
      {error && <div className="error-message" style={{ marginTop: "16px" }}>{error}</div>}
      {message && <div style={{ marginTop: "16px", padding: "12px", background: "rgba(16,185,129,0.1)", color: "#10B981", borderRadius: "8px", fontSize: "14px" }}>{message}</div>}
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
export default function Stock() {
  const [tab, setTab] = useState("sale");

  return (
    <div className="page-content">
      <div className="tabs" style={{ marginBottom: "20px", display: "flex", overflowX: "auto", borderBottom: "1px solid var(--border-color)" }}>
        <button className={`tab-button ${tab === "sale" ? "active" : ""}`} onClick={() => setTab("sale")} style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <TrendingUp size={18} /> Record a Sale
        </button>
        <button className={`tab-button ${tab === "adjustment" ? "active" : ""}`} onClick={() => setTab("adjustment")} style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <Edit3 size={18} /> Stock Adjustment
        </button>
        <button className={`tab-button ${tab === "add-medicine" ? "active" : ""}`} onClick={() => setTab("add-medicine")} style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <Plus size={18} /> Add Medicine
        </button>
        <button className={`tab-button ${tab === "ledger" ? "active" : ""}`} onClick={() => setTab("ledger")} style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <ClipboardList size={18} /> Stock Ledger
        </button>
        <button className={`tab-button ${tab === "reorder" ? "active" : ""}`} onClick={() => setTab("reorder")} style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <Package size={18} /> Reorder List
        </button>
        <button className={`tab-button ${tab === "smart-reorder" ? "active" : ""}`} onClick={() => setTab("smart-reorder")} style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <Lightbulb size={18} /> Smart Reorder
        </button>
      </div>
      
      <div style={{ position: "relative", minHeight: "400px" }}>
        {tab === "sale" && <RecordSaleTab />}
        {tab === "adjustment" && <AdjustmentTab />}
        {tab === "add-medicine" && <AddMedicineTab />}
        {tab === "ledger" && <StockLedgerTab />}
        {tab === "reorder" && <ReorderListTab />}
        {tab === "smart-reorder" && <SmartReorderTab />}
      </div>
    </div>
  );
}