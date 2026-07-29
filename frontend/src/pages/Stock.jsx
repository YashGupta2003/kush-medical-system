import { useEffect, useState } from "react";
import { api } from "../api/client.js";

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
      setConfirmation(`✅ Recorded: ${qtySold} sold. Stock is now ${updated.current_stock}.`);
      setQtySold("");
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <div className="card">
        <h2>Record a Sale</h2>
        <p style={{ color: "#666", fontSize: 13 }}>
          Search the medicine that was just sold, check current stock levels, then enter how many pieces were sold.
        </p>
        <input
          style={{ width: "100%" }}
          placeholder="Search medicine name (e.g. AMLOKIND-AT TABS)..."
          value={query}
          onChange={(e) => { setQuery(e.target.value); setSelected(null); setSnapshot(null); }}
        />
        {results.length > 0 && (
          <table style={{ marginTop: 10 }}>
            <tbody>
              {results.map((m) => (
                <tr key={m.id} onClick={() => selectMedicine(m)} style={{ cursor: "pointer" }}>
                  <td><strong>{m.particulars}</strong></td>
                  <td style={{ color: "#888" }}>{m.unit || "—"}</td>
                  <td>Stock: {m.current_stock ?? 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {snapshot && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>{snapshot.medicine_name}</h3>

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
            <div className="last-purchase-card">
              <div className="title">📦 Last Delivery Received</div>
              <div>
                <strong>{snapshot.last_purchase.qty_received}</strong> units
                {snapshot.last_purchase.free_qty_received > 0 && <> (+{snapshot.last_purchase.free_qty_received} free)</>}
                {" "}from <strong>{snapshot.last_purchase.distributor_name || "distributor"}</strong>
              </div>
              <div>Rate: ₹{snapshot.last_purchase.rate ?? "—"} · MRP: ₹{snapshot.last_purchase.mrp ?? "—"}</div>
              <div>Date: {snapshot.last_purchase.purchase_date ? new Date(snapshot.last_purchase.purchase_date).toLocaleDateString() : "—"}</div>
            </div>
          ) : (
            <p style={{ color: "#888", fontSize: 13 }}>No purchase history found yet for this medicine.</p>
          )}

          <form onSubmit={handleRecordSale} style={{ display: "flex", gap: 8, alignItems: "flex-end", marginTop: 12 }}>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: 12, color: "#666" }}>Quantity Sold</label>
              <input
                type="number" min="0.01" step="0.01" required
                style={{ width: "100%" }}
                value={qtySold}
                onChange={(e) => setQtySold(e.target.value)}
              />
            </div>
            <button type="submit" disabled={saving}>{saving ? "Saving..." : "Record sale"}</button>
          </form>

          {confirmation && <p style={{ color: "#16a34a", marginTop: 10 }}>{confirmation}</p>}
          {error && <p style={{ color: "#b91c1c", marginTop: 10 }}>{error}</p>}
        </div>
      )}
    </div>
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
      setMessage(`✅ Stock updated for ${selected.particulars}. New total balance: ${res.resulting_balance}`);
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
    <div className="card">
      <h2>Manual Physical Inventory Adjustment</h2>
      <p style={{ color: "#666", fontSize: 13 }}>
        Directly align stock records with physical shelf counts (e.g. damaged stock, manual audit counts). Every change is audited in the Stock Ledger.
      </p>
      <form onSubmit={handleAdjust}>
        <div style={{ marginBottom: 12 }}>
          <label style={{ fontSize: 12, color: "#666" }}>Select Medicine</label>
          <input
            style={{ width: "100%" }}
            placeholder="Search medicine to adjust..."
            value={selected ? selected.particulars : query}
            onChange={(e) => { setQuery(e.target.value); setSelected(null); }}
          />
          {results.length > 0 && !selected && (
            <table style={{ marginTop: 6 }}>
              <tbody>
                {results.map((m) => (
                  <tr key={m.id} style={{ cursor: "pointer" }} onClick={() => { setSelected(m); setNewStock(m.current_stock ?? 0); setResults([]); }}>
                    <td><strong>{m.particulars}</strong></td>
                    <td>Current: {m.current_stock ?? 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {selected && (
          <>
            <div style={{ display: "flex", gap: 12, marginBottom: 12 }}>
              <div style={{ flex: 1 }}>
                <label style={{ fontSize: 12, color: "#666" }}>New Physical Stock Count</label>
                <input
                  type="number" step="0.01" required
                  style={{ width: "100%" }}
                  value={newStock}
                  onChange={(e) => setNewStock(e.target.value)}
                />
              </div>
              <div style={{ flex: 2 }}>
                <label style={{ fontSize: 12, color: "#666" }}>Audit Note / Reason</label>
                <input
                  placeholder="e.g. Shelf audit, broken bottle discarded"
                  style={{ width: "100%" }}
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                />
              </div>
            </div>
            <button type="submit" disabled={saving}>{saving ? "Saving..." : "Save Adjustment"}</button>
          </>
        )}
      </form>
      {message && <p style={{ color: "#16a34a", marginTop: 10 }}>{message}</p>}
      {error && <p style={{ color: "#b91c1c", marginTop: 10 }}>{error}</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// TAB 3: Stock Ledger Audit Trail
// ---------------------------------------------------------------------------
function StockLedgerTab() {
  const [ledger, setLedger] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getStockLedger({ limit: 50 })
      .then((res) => setLedger(res.items || res))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="card">
      <h2>Stock Ledger Audit Trail</h2>
      <p style={{ color: "#666", fontSize: 13 }}>
        Immutable history of every inventory change across bills, sales, and adjustments.
      </p>
      {loading ? (
        <p>Loading ledger entries...</p>
      ) : ledger.length === 0 ? (
        <p style={{ color: "#888" }}>No ledger movements recorded yet.</p>
      ) : (
        <table style={{ marginTop: 12 }}>
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Medicine</th>
              <th>Reason</th>
              <th>Change Qty</th>
              <th>Resulting Balance</th>
              <th>Note / Ref</th>
            </tr>
          </thead>
          <tbody>
            {ledger.map((row) => (
              <tr key={row.id}>
                <td>{new Date(row.created_at).toLocaleString()}</td>
                <td><strong>{row.medicine_name || row.medicine_id}</strong></td>
                <td>
                  <span className={`badge ${row.reason === "bill_received" ? "auto" : row.reason === "sale" ? "learned" : "manual"}`}>
                    {row.reason}
                  </span>
                </td>
                <td style={{ color: row.change_qty > 0 ? "#16a34a" : "#dc2626", fontWeight: "bold" }}>
                  {row.change_qty > 0 ? `+${row.change_qty}` : row.change_qty}
                </td>
                <td><strong>{row.resulting_balance}</strong></td>
                <td>{row.note || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
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
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={(e) => e.stopPropagation()}>
        <h3 style={{ marginTop: 0 }}>Add item to reorder list</h3>
        <div className="tabs">
          <button className={`tab-button ${mode === "existing" ? "active" : ""}`} onClick={() => setMode("existing")}>Existing medicine</button>
          <button className={`tab-button ${mode === "custom" ? "active" : ""}`} onClick={() => setMode("custom")}>New item</button>
        </div>

        <form onSubmit={handleSubmit}>
          {mode === "existing" ? (
            <div style={{ marginBottom: 10 }}>
              <label style={{ fontSize: 12, color: "#666" }}>Search medicine</label>
              <input
                style={{ width: "100%" }}
                value={selectedMedicine ? selectedMedicine.particulars : query}
                onChange={(e) => { setQuery(e.target.value); setSelectedMedicine(null); }}
                placeholder="Start typing..."
              />
              {results.length > 0 && !selectedMedicine && (
                <table style={{ marginTop: 6 }}>
                  <tbody>
                    {results.map((m) => (
                      <tr key={m.id} style={{ cursor: "pointer" }} onClick={() => { setSelectedMedicine(m); setResults([]); }}>
                        <td>{m.particulars}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          ) : (
            <div style={{ marginBottom: 10 }}>
              <label style={{ fontSize: 12, color: "#666" }}>Item name</label>
              <input style={{ width: "100%" }} value={customName} onChange={(e) => setCustomName(e.target.value)}
                placeholder="e.g. Listerine Mouthwash 250ml" />
            </div>
          )}

          <div style={{ marginBottom: 10 }}>
            <label style={{ fontSize: 12, color: "#666" }}>Order from distributor (optional)</label>
            <input style={{ width: "100%" }} value={distributorName} onChange={(e) => setDistributorName(e.target.value)}
              placeholder="e.g. RATHORE MEDICOS" />
          </div>

          <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: 12, color: "#666" }}>Quantity needed</label>
              <input type="number" min="1" style={{ width: "100%" }} value={quantity} onChange={(e) => setQuantity(e.target.value)} />
            </div>
          </div>

          <div style={{ marginBottom: 14 }}>
            <label style={{ fontSize: 12, color: "#666" }}>Note (optional)</label>
            <input style={{ width: "100%" }} value={note} onChange={(e) => setNote(e.target.value)} />
          </div>

          {error && <p style={{ color: "#b91c1c", fontSize: 13 }}>{error}</p>}

          <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
            <button type="button" className="secondary" onClick={onClose}>Cancel</button>
            <button type="submit" disabled={saving}>{saving ? "Adding..." : "Add to list"}</button>
          </div>
        </form>
      </div>
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
    <div>
      <div className="card">
        <div className="flex-between">
          <div>
            <h2 style={{ marginBottom: 4 }}>Reorder List</h2>
            <p style={{ color: "#666", fontSize: 13, margin: 0 }}>
              Grouped by distributor, so you know exactly who to call and what to ask for.
              {totalItems > 0 && <> <strong>{totalItems}</strong> item{totalItems === 1 ? "" : "s"} need attention.</>}
            </p>
          </div>
          <button onClick={() => setShowModal(true)}>+ Add manual item</button>
        </div>
      </div>

      {loading && <p>Loading...</p>}
      {!loading && groups.length === 0 && (
        <div className="card"><p style={{ color: "#666" }}>Nothing to reorder right now — stock levels look healthy. 🎉</p></div>
      )}

      {groups.map((group) => {
        const isFallback = group.distributor_name.includes("Unknown") || group.distributor_name.includes("Unassigned");
        return (
          <div className="distributor-group" key={group.distributor_name}>
            <div className={`distributor-group-header ${isFallback ? "fallback" : ""}`}>
              <span className="name">{isFallback ? "⚠️ " : "🏢 "}{group.distributor_name}</span>
              <span className="count">{group.items.length} item{group.items.length === 1 ? "" : "s"}</span>
            </div>
            {group.items.map((item, idx) => (
              <div className="reorder-item-row" key={item.id ?? `auto-${item.medicine_id}-${idx}`}>
                <div>
                  <div className="reorder-item-name">{item.name}</div>
                  <div className="reorder-item-meta">
                    {item.current_stock != null && <>Stock: {item.current_stock}{item.low_stock_threshold != null && <> (below {item.low_stock_threshold})</>} · </>}
                    {item.last_qty_received != null && <>Last order: {item.last_qty_received} units @ ₹{item.last_rate ?? "—"} </>}
                    {item.last_purchase_date && <>on {new Date(item.last_purchase_date).toLocaleDateString()} </>}
                    {item.quantity_needed != null && <>· Need: {item.quantity_needed}</>}
                    {item.note && <> · "{item.note}"</>}
                  </div>
                </div>
                <div className="reorder-item-actions">
                  <span className={`badge ${item.source === "auto_low_stock" ? "unmatched" : "manual"}`}>
                    {item.source === "auto_low_stock" ? "Low stock" : "Manually added"}
                  </span>
                  {item.id && (
                    <>
                      <button onClick={() => handleFulfill(item.id)}>Mark Fulfilled</button>
                      <button className="secondary" onClick={() => handleRemove(item.id)}>Remove</button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        );
      })}

      {showModal && <AddReorderItemModal onClose={() => setShowModal(false)} onAdded={refresh} />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Stock Component with 4 Tabs
// ---------------------------------------------------------------------------
export default function Stock() {
  const [tab, setTab] = useState("sale");

  return (
    <div>
      <div className="tabs">
        <button className={`tab-button ${tab === "sale" ? "active" : ""}`} onClick={() => setTab("sale")}>Record a Sale</button>
        <button className={`tab-button ${tab === "adjustment" ? "active" : ""}`} onClick={() => setTab("adjustment")}>Stock Adjustment</button>
        <button className={`tab-button ${tab === "ledger" ? "active" : ""}`} onClick={() => setTab("ledger")}>Stock Ledger</button>
        <button className={`tab-button ${tab === "reorder" ? "active" : ""}`} onClick={() => setTab("reorder")}>Reorder List</button>
      </div>
      {tab === "sale" && <RecordSaleTab />}
      {tab === "adjustment" && <AdjustmentTab />}
      {tab === "ledger" && <StockLedgerTab />}
      {tab === "reorder" && <ReorderListTab />}
    </div>
  );
}