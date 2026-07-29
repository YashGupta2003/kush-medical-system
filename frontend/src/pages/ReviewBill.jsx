import { useEffect, useRef, useState, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../api/client.js";

const FIELD_LABELS = {
  qty: "Qty", free_qty: "Free", mrp: "MRP", rate: "Rate",
  discount_pct: "Disc %", special_discount_pct: "Sp. Disc %", gst_pct: "GST %",
};
const EDITABLE_FIELDS = Object.keys(FIELD_LABELS);

// ---------------------------------------------------------------------------
// Mirrors app/services/cost_calculator.py compute_cost_per_unit() exactly,
// so the pill on screen always matches what the backend will actually save
// - including live updates as the user edits fields, instead of showing the
// stale number from the original (possibly OCR-misread) parse.
// ---------------------------------------------------------------------------
function computeCostPerUnit(row) {
  const qty = Number(row.qty) || 0;
  const free = Number(row.free_qty) || 0;
  const rate = Number(row.rate) || 0;
  const disc1 = Number(row.discount_pct) || 0;
  const disc2 = Number(row.special_discount_pct) || 0;
  const gst = Number(row.gst_pct) || 0;

  const effectiveUnits = qty + free;
  if (effectiveUnits <= 0) return 0;

  const gross = rate * qty;
  const afterDiscount1 = gross * (1 - disc1 / 100);
  const afterDiscount2 = afterDiscount1 * (1 - disc2 / 100);
  const netLanded = afterDiscount2 * (1 + gst / 100);

  return netLanded / effectiveUnits;
}

// ---------------------------------------------------------------------------
// Search-and-link widget for line items that OCR/fuzzy-matching couldn't
// resolve to a medicine on their own. Without this, medicine_id stays null
// forever for unmatched items, and /bills/confirm silently skips the master
// list update, stock increment, AND expiry batch creation for that item
// (all three require a non-null medicine_id on the backend).
// ---------------------------------------------------------------------------
function MedicineLinkPicker({ onLink }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([]);
      return;
    }
    setSearching(true);
    const t = setTimeout(() => {
      api.browseMedicines({ q: query, page: 1, page_size: 8 })
        .then((d) => setResults(d.items))
        .finally(() => setSearching(false));
    }, 250);
    return () => clearTimeout(t);
  }, [query]);

  return (
    <div style={{ marginTop: 6 }}>
      <input
        style={{ width: "100%" }}
        placeholder="Type to search the master list and link the correct medicine..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      {searching && <p style={{ fontSize: 12, color: "#888", margin: "4px 0 0" }}>Searching...</p>}
      {results.length > 0 && (
        <table style={{ marginTop: 6 }}>
          <tbody>
            {results.map((m) => (
              <tr
                key={m.id}
                style={{ cursor: "pointer" }}
                onClick={() => { onLink(m); setQuery(""); setResults([]); }}
              >
                <td>{m.particulars}</td>
                <td style={{ color: "#888" }}>{m.unit}</td>
                <td><button className="secondary">Link this</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Left pane: zoomable/pannable bill image with click-to-fill rectangle select
// ---------------------------------------------------------------------------
function BillImageViewer({ billId, pickingField, onRegionSelected }) {
  const containerRef = useRef(null);
  const imgRef = useRef(null);
  const [zoom, setZoom] = useState(1);
  const [naturalSize, setNaturalSize] = useState(null);
  const [drag, setDrag] = useState(null);
  const [panning, setPanning] = useState(null);

  const imgUrl = api.getBillImageUrl(billId);

  function handleMouseDown(e) {
    if (pickingField) {
      const rect = imgRef.current.getBoundingClientRect();
      setDrag({ startX: e.clientX, startY: e.clientY, curX: e.clientX, curY: e.clientY, imgRect: rect });
    } else {
      setPanning({
        startX: e.clientX, startY: e.clientY,
        scrollLeft: containerRef.current.scrollLeft, scrollTop: containerRef.current.scrollTop,
      });
    }
  }

  function handleMouseMove(e) {
    if (drag) {
      setDrag((d) => ({ ...d, curX: e.clientX, curY: e.clientY }));
    } else if (panning) {
      containerRef.current.scrollLeft = panning.scrollLeft - (e.clientX - panning.startX);
      containerRef.current.scrollTop = panning.scrollTop - (e.clientY - panning.startY);
    }
  }

  function handleMouseUp() {
    if (drag && naturalSize) {
      const { startX, startY, curX, curY, imgRect } = drag;
      const left = Math.min(startX, curX), right = Math.max(startX, curX);
      const top = Math.min(startY, curY), bottom = Math.max(startY, curY);

      const fracX0 = (left - imgRect.left) / imgRect.width;
      const fracX1 = (right - imgRect.left) / imgRect.width;
      const fracY0 = (top - imgRect.top) / imgRect.height;
      const fracY1 = (bottom - imgRect.top) / imgRect.height;

      const x0 = Math.round(fracX0 * naturalSize.w);
      const x1 = Math.round(fracX1 * naturalSize.w);
      const y0 = Math.round(fracY0 * naturalSize.h);
      const y1 = Math.round(fracY1 * naturalSize.h);

      if (x1 - x0 > 4 && y1 - y0 > 4) {
        onRegionSelected({ x0, y0, x1, y1 });
      }
    }
    setDrag(null);
    setPanning(null);
  }

  return (
    <div className="card image-viewer-card" style={{ padding: 12 }}>
      <div className="flex-between" style={{ marginBottom: 10 }}>
        <strong style={{ fontSize: 14 }}>📄 Original bill</strong>
        <div style={{ display: "flex", gap: 6 }}>
          <button className="secondary" onClick={() => setZoom((z) => Math.max(0.3, +(z - 0.25).toFixed(2)))}>−</button>
          <span style={{ fontSize: 13, alignSelf: "center", minWidth: 40, textAlign: "center" }}>{Math.round(zoom * 100)}%</span>
          <button className="secondary" onClick={() => setZoom((z) => Math.min(4, +(z + 0.25).toFixed(2)))}>+</button>
          <button className="secondary" onClick={() => setZoom(1)}>Reset</button>
        </div>
      </div>
      {pickingField && (
        <p style={{ background: "#fef3c7", padding: 10, borderRadius: 8, fontSize: 13, marginBottom: 10 }}>
          🎯 Drag a box around the correct value for <strong>{FIELD_LABELS[pickingField.field] || pickingField.field}</strong>.
        </p>
      )}
      <div
        ref={containerRef}
        className="image-scroll-area"
        style={{ cursor: pickingField ? "crosshair" : panning ? "grabbing" : "grab" }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={() => { setDrag(null); setPanning(null); }}
      >
        <img
          ref={imgRef}
          src={imgUrl}
          alt="Bill"
          draggable={false}
          onLoad={(e) => setNaturalSize({ w: e.target.naturalWidth, h: e.target.naturalHeight })}
          style={{
            width: "100%", display: "block", userSelect: "none",
            transform: `scale(${zoom})`, transformOrigin: "top left",
          }}
        />
        {drag && (
          <div
            style={{
              position: "fixed",
              left: Math.min(drag.startX, drag.curX), top: Math.min(drag.startY, drag.curY),
              width: Math.abs(drag.curX - drag.startX), height: Math.abs(drag.curY - drag.startY),
              border: "2px solid #2563eb", background: "rgba(37,99,235,0.15)", pointerEvents: "none",
            }}
          />
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// One editable line-item card
// ---------------------------------------------------------------------------
function ItemCard({ row, applied, onFieldChange, onToggleApply, onPickField, pickingField, onLinkMedicine, onRemove }) {
  const isPicking = (field) => pickingField && pickingField.itemId === row.id && pickingField.field === field;

  return (
    <div className="item-card">
      <div className="item-card-header">
        <input
          value={row.raw_name || ""}
          placeholder="Medicine name as printed on the bill..."
          onChange={(e) => onFieldChange(row.id, "raw_name", e.target.value)}
        />
        <button
          className={`icon-btn ${isPicking("raw_name") ? "" : "secondary"}`}
          title="Pick name from image"
          onClick={() => onPickField(row.id, "raw_name")}
        >🎯</button>
        <button
          className="icon-btn secondary"
          title="Remove this item"
          onClick={() => onRemove(row.id)}
        >🗑️</button>
      </div>

      <div className="item-match-row">
        {row.medicine_id && row.suggested_medicine_name ? (
          <span className={`badge ${row.match_status}`}>
            {row.match_status === "learned" ? "Learned match: "
              : row.match_status === "auto" ? "Auto-matched: "
              : row.match_status === "manual" ? "Linked: " : ""}
            {row.suggested_medicine_name} ({Math.round(row.match_confidence || 0)}%)
          </span>
        ) : (
          <>
            <span className="badge unmatched">Unmatched — pick manually</span>
            <MedicineLinkPicker onLink={(medicine) => onLinkMedicine(row.id, medicine)} />
          </>
        )}
      </div>

      <div className="item-fields-grid">
        {EDITABLE_FIELDS.map((f) => (
          <div className="field-group" key={f}>
            <label>{FIELD_LABELS[f]}</label>
            <div className="field-group-inner">
              <input
                type="number"
                value={row[f] ?? ""}
                onChange={(e) => onFieldChange(row.id, f, e.target.value)}
              />
              <button
                className={`icon-btn ${isPicking(f) ? "" : "secondary"}`}
                title={`Pick ${FIELD_LABELS[f]} from image`}
                onClick={() => onPickField(row.id, f)}
              >🎯</button>
            </div>
          </div>
        ))}
      </div>

      <div className="item-card-footer">
        <span className="cost-pill">Cost/unit: ₹{computeCostPerUnit(row).toFixed(2)}</span>
        <label className="update-list-toggle">
          <input
            type="checkbox"
            checked={!!applied}
            disabled={!row.medicine_id}
            onChange={(e) => onToggleApply(row.id, e.target.checked)}
          />
          Update master list
          {!row.medicine_id && (
            <span style={{ color: "#999", fontSize: 11 }}>(link a medicine first)</span>
          )}
        </label>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main review page
// ---------------------------------------------------------------------------
export default function ReviewBill() {
  const { billId } = useParams();
  const [bill, setBill] = useState(null);
  const [rows, setRows] = useState({});
  const [applyFlags, setApplyFlags] = useState({});
  const [stage, setStage] = useState("reviewing");
  const [changeSummary, setChangeSummary] = useState(null);
  const [error, setError] = useState(null);
  const [pickingField, setPickingField] = useState(null);
  const [regionLoading, setRegionLoading] = useState(false);

  useEffect(() => {
    api.getBill(billId).then((b) => {
      setBill(b);
      const initialRows = {};
      const initialFlags = {};
      b.items.forEach((item) => {
        initialRows[item.id] = { ...item };
        initialFlags[item.id] = item.match_status !== "unmatched";
      });
      setRows(initialRows);
      setApplyFlags(initialFlags);
    });
  }, [billId]);

  function updateField(itemId, field, value) {
    setRows((prev) => ({ ...prev, [itemId]: { ...prev[itemId], [field]: value } }));
  }

  // Called when the user picks a medicine from MedicineLinkPicker for a
  // previously-unmatched row. This is the piece that was missing entirely -
  // without setting medicine_id here, /bills/confirm has nothing to attach
  // the master-list update, stock increment, or expiry batch to, no matter
  // what the user typed into the other fields.
  function handleLinkMedicine(itemId, medicine) {
    setRows((prev) => ({
      ...prev,
      [itemId]: {
        ...prev[itemId],
        medicine_id: medicine.id,
        suggested_medicine_name: medicine.particulars,
        match_status: "manual",
        match_confidence: 100,
      },
    }));
    setApplyFlags((prev) => ({ ...prev, [itemId]: true }));
  }

  // Fallback for bills where OCR found no table at all (or missed a row) -
  // adds one blank, fully-editable row backed by a real BillItem in the DB,
  // so it flows through the exact same link/edit/confirm path as every
  // OCR-extracted item.
  const [addingItem, setAddingItem] = useState(false);
  async function handleAddItem() {
    setAddingItem(true);
    setError(null);
    try {
      const newItem = await api.addBillItem(billId);
      setRows((prev) => ({ ...prev, [newItem.id]: { ...newItem } }));
      setApplyFlags((prev) => ({ ...prev, [newItem.id]: false }));
    } catch (err) {
      setError(err.message);
    } finally {
      setAddingItem(false);
    }
  }

  async function handleRemoveItem(itemId) {
    setError(null);
    try {
      await api.removeBillItem(billId, itemId);
      setRows((prev) => {
        const next = { ...prev };
        delete next[itemId];
        return next;
      });
      setApplyFlags((prev) => {
        const next = { ...prev };
        delete next[itemId];
        return next;
      });
    } catch (err) {
      setError(err.message);
    }
  }

  const handleRegionSelected = useCallback(async (box) => {
    if (!pickingField) return;
    setRegionLoading(true);
    try {
      const result = await api.reprocessRegion(billId, box);
      const { itemId, field } = pickingField;
      if (field === "raw_name") {
        updateField(itemId, field, result.text.trim());
      } else {
        const numeric = parseFloat(result.text.replace(/[^0-9.]/g, ""));
        if (!Number.isNaN(numeric)) {
          updateField(itemId, field, numeric);
        } else {
          setError(`Could not read a number from that region (got "${result.text}"). Try a tighter box.`);
        }
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setRegionLoading(false);
      setPickingField(null);
    }
  }, [pickingField, billId]);

  const itemsToApplyCount = Object.values(applyFlags).filter(Boolean).length;

  const itemsMissingExpiry = Object.values(rows).filter(
    (r) => r.medicine_id && (!r.exp_date || !String(r.exp_date).trim())
  );

  function handleProceedClick() {
    if (itemsMissingExpiry.length > 0) {
      setStage("expiry_check");
    } else {
      setStage("confirming");
    }
  }

  async function handleFinalConfirm() {
    setStage("applying");
    setError(null);
    try {
      const parseNum = (val) => {
        const parsed = Number(val);
        return Number.isNaN(parsed) ? 0 : (parsed || 0);
      };
      
      const items = Object.values(rows).map((r) => ({
        id: r.id,
        raw_name: r.raw_name,
        qty: parseNum(r.qty),
        free_qty: parseNum(r.free_qty),
        mrp: parseNum(r.mrp),
        rate: parseNum(r.rate),
        discount_pct: parseNum(r.discount_pct),
        special_discount_pct: parseNum(r.special_discount_pct),
        gst_pct: parseNum(r.gst_pct),
        exp_date: r.exp_date || null,
        medicine_id: r.medicine_id || null,
        apply_to_master_list: !!applyFlags[r.id],
      }));
      const summary = await api.confirmBill({ bill_id: Number(billId), items });
      setChangeSummary(summary);
      setStage("done");
    } catch (err) {
      setError(err.message);
      setStage("reviewing");
    }
  }

  if (!bill) return <p>Loading...</p>;

  if (stage === "done" && changeSummary) {
    return (
      <div className="card">
        <h2>✅ Master list updated</h2>
        {changeSummary.length === 0 && <p>No master rate list changes were made.</p>}
        <table>
          <thead><tr><th>Medicine</th><th>Column</th><th>Old value</th><th>New value</th><th>Status</th></tr></thead>
          <tbody>
            {changeSummary.map((c, i) => (
              <tr key={i}>
                <td>{c.medicine_name}</td>
                <td>{c.field === "net_rate" ? "Cost price (NET RATE)" : "MRP"}</td>
                <td>{c.old_value ?? "—"}</td>
                <td><strong>{c.new_value ?? "—"}</strong></td>
                <td><span className="badge auto">found &amp; updated</span></td>
              </tr>
            ))}
          </tbody>
        </table>
        <Link to="/"><button style={{ marginTop: 16 }}>View full updated medicine list</button></Link>
      </div>
    );
  }

  if (stage === "expiry_check") {
    return (
      <div className="card" style={{ borderLeft: "4px solid #ea580c" }}>
        <h2>📝 A few items are missing an expiry date</h2>
        <p style={{ color: "#666", fontSize: 13 }}>
          The bill photo didn't show a readable expiry date for these items. Check the actual
          packet/strip and enter it here — this powers your Expiry Tracker alerts later. You can
          also skip and fill these in afterwards from the Expiry page.
        </p>
        {itemsMissingExpiry.map((r) => (
          <div key={r.id} className="reorder-item-row">
            <div className="reorder-item-name">{r.raw_name}</div>
            <input type="date" onChange={(e) => updateField(r.id, "exp_date", e.target.value)} />
          </div>
        ))}
        <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
          <button onClick={() => setStage("confirming")}>Continue</button>
          <button className="secondary" onClick={() => setStage("reviewing")}>Back to review</button>
        </div>
      </div>
    );
  }

  if (stage === "confirming") {
    return (
      <div className="card">
        <h2>Update the master rate list now?</h2>
        <p>
          You're about to update <strong>{itemsToApplyCount}</strong> medicine
          {itemsToApplyCount === 1 ? "" : "s"} in your master rate list based on this bill.
        </p>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={handleFinalConfirm}>Yes, update the list</button>
          <button className="secondary" onClick={() => setStage("reviewing")}>No, let me review again</button>
        </div>
      </div>
    );
  }

  if (stage === "applying") {
    return <div className="card"><p>Updating master list...</p></div>;
  }

  return (
    <div>
      <div className="card">
        <div className="flex-between">
          <div>
            <h2 style={{ marginBottom: 4 }}>Review bill #{bill.id}</h2>
            <p style={{ color: "#666", fontSize: 13, margin: 0 }}>
              {bill.distributor_name || "Unknown distributor"} · {bill.invoice_no || "no invoice no."} ·
              {" "}{bill.year}-{String(bill.month).padStart(2, "0")}
            </p>
          </div>
          <button onClick={handleProceedClick} disabled={Object.keys(rows).length === 0}>
            Looks good — proceed ({itemsToApplyCount} to update)
          </button>
        </div>
        {bill.status === "needs_attention" && (
          <p style={{ background: "#fee2e2", padding: 10, borderRadius: 8, fontSize: 13, marginTop: 10 }}>
            ⚠️ This bill needs extra attention: {bill.needs_attention_reason}
          </p>
        )}
        {error && <p style={{ color: "#b91c1c", marginTop: 8 }}>{error}</p>}
        {regionLoading && <p style={{ color: "#666", marginTop: 8 }}>Reading selected region...</p>}
      </div>

      <div className="review-grid">
        <BillImageViewer billId={bill.id} pickingField={pickingField} onRegionSelected={handleRegionSelected} />

        <div>
          <div className="flex-between" style={{ marginBottom: 10 }}>
            <p style={{ fontSize: 13, color: "#666", margin: 0 }}>
              Click 🎯 next to any field, then drag a box around the correct value on the image to re-read just that spot.
            </p>
            <button className="secondary" onClick={handleAddItem} disabled={addingItem}>
              {addingItem ? "Adding..." : "+ Add item manually"}
            </button>
          </div>

          {Object.keys(rows).length === 0 && (
            <div className="card" style={{ borderLeft: "4px solid #ea580c" }}>
              <p style={{ margin: 0, fontSize: 13, color: "#666" }}>
                No items could be read automatically from this bill. Use "+ Add item manually" above
                to enter each line item by hand, using the original bill image on the left as reference.
              </p>
            </div>
          )}

          {Object.values(rows).map((r) => (
            <ItemCard
              key={r.id}
              row={r}
              applied={applyFlags[r.id]}
              onFieldChange={updateField}
              onToggleApply={(id, checked) => setApplyFlags((prev) => ({ ...prev, [id]: checked }))}
              onPickField={(id, field) => setPickingField({ itemId: id, field })}
              pickingField={pickingField}
              onLinkMedicine={handleLinkMedicine}
              onRemove={handleRemoveItem}
            />
          ))}
        </div>
      </div>
    </div>
  );
}