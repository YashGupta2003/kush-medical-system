import { useEffect, useRef, useState, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../api/client.js";

const EDITABLE_FIELDS = ["qty", "free_qty", "mrp", "rate", "discount_pct", "special_discount_pct", "gst_pct"];

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

  const displayWidth = naturalSize ? naturalSize.w * zoom * 0.4 : undefined;

  return (
    <div className="card" style={{ padding: 8 }}>
      <div className="flex-between" style={{ marginBottom: 8 }}>
        <strong style={{ fontSize: 13 }}>Original bill</strong>
        <div style={{ display: "flex", gap: 6 }}>
          <button className="secondary" onClick={() => setZoom((z) => Math.max(0.3, z - 0.25))}>−</button>
          <span style={{ fontSize: 13, alignSelf: "center" }}>{Math.round(zoom * 100)}%</span>
          <button className="secondary" onClick={() => setZoom((z) => Math.min(4, z + 0.25))}>+</button>
          <button className="secondary" onClick={() => setZoom(1)}>Reset</button>
        </div>
      </div>
      {pickingField && (
        <p style={{ background: "#fef3c7", padding: 8, borderRadius: 6, fontSize: 13 }}>
          Drag a box around the correct value on the image for <strong>{pickingField.field}</strong>.
        </p>
      )}
      <div
        ref={containerRef}
        style={{
          overflow: "auto", height: 520, border: "1px solid #eee", borderRadius: 8,
          cursor: pickingField ? "crosshair" : panning ? "grabbing" : "grab",
          position: "relative", background: "#fafafa",
        }}
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
          style={{ width: displayWidth, userSelect: "none", display: "block" }}
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

  async function handleFinalConfirm() {
    setStage("applying");
    setError(null);
    try {
      const items = Object.values(rows).map((r) => ({
        id: r.id,
        raw_name: r.raw_name,
        qty: Number(r.qty) || 0,
        free_qty: Number(r.free_qty) || 0,
        mrp: Number(r.mrp) || 0,
        rate: Number(r.rate) || 0,
        discount_pct: Number(r.discount_pct) || 0,
        special_discount_pct: Number(r.special_discount_pct) || 0,
        gst_pct: Number(r.gst_pct) || 0,
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
            <h2>Review bill #{bill.id}</h2>
            <p style={{ color: "#666", fontSize: 13 }}>
              {bill.distributor_name || "Unknown distributor"} · {bill.invoice_no || "no invoice no."} ·
              {" "}{bill.year}-{String(bill.month).padStart(2, "0")}
            </p>
          </div>
          <button onClick={() => setStage("confirming")}>
            Looks good — proceed ({itemsToApplyCount} to update)
          </button>
        </div>
        {bill.status === "needs_attention" && (
          <p style={{ background: "#fee2e2", padding: 10, borderRadius: 6, fontSize: 13, marginTop: 8 }}>
            ⚠️ This bill needs extra attention: {bill.needs_attention_reason}
          </p>
        )}
        {error && <p style={{ color: "#b91c1c" }}>{error}</p>}
        {regionLoading && <p style={{ color: "#666" }}>Reading selected region...</p>}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, alignItems: "start" }}>
        <BillImageViewer billId={bill.id} pickingField={pickingField} onRegionSelected={handleRegionSelected} />

        <div className="card" style={{ overflowX: "auto" }}>
          <p style={{ fontSize: 12, color: "#666" }}>
            Click the 🎯 next to any field, then drag a box around the correct value on the image
            to the left to re-read just that spot.
          </p>
          {Object.values(rows).map((r) => (
            <div key={r.id} style={{ border: "1px solid #eee", borderRadius: 8, padding: 10, marginBottom: 10 }}>
              <div style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 6 }}>
                <input
                  style={{ flex: 1 }}
                  value={r.raw_name || ""}
                  onChange={(e) => updateField(r.id, "raw_name", e.target.value)}
                />
                <button
                  className="secondary"
                  title="Pick from image"
                  onClick={() => setPickingField({ itemId: r.id, field: "raw_name" })}
                >🎯</button>
              </div>
              <div style={{ marginBottom: 6 }}>
                {r.suggested_medicine_name ? (
                  <span className={`badge ${r.match_status}`}>
                    {r.suggested_medicine_name} ({Math.round(r.match_confidence || 0)}%)
                  </span>
                ) : (
                  <span className="badge unmatched">no match — pick manually</span>
                )}
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 6 }}>
                {EDITABLE_FIELDS.map((f) => (
                  <div key={f}>
                    <label style={{ fontSize: 11, color: "#666" }}>{f}</label>
                    <div style={{ display: "flex", gap: 4 }}>
                      <input
                        type="number"
                        style={{ width: "100%" }}
                        value={r[f] ?? ""}
                        onChange={(e) => updateField(r.id, f, e.target.value)}
                      />
                      <button
                        className="secondary"
                        title="Pick from image"
                        onClick={() => setPickingField({ itemId: r.id, field: f })}
                      >🎯</button>
                    </div>
                  </div>
                ))}
              </div>
              <div style={{ marginTop: 6, fontSize: 13, display: "flex", justifyContent: "space-between" }}>
                <span>Cost/unit: <strong>{r.computed_cost_per_unit}</strong></span>
                <label style={{ fontSize: 12 }}>
                  <input
                    type="checkbox"
                    checked={!!applyFlags[r.id]}
                    onChange={(e) => setApplyFlags((prev) => ({ ...prev, [r.id]: e.target.checked }))}
                  /> Update master list
                </label>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
