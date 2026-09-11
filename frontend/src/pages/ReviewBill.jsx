import { useEffect, useRef, useState, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../api/client.js";
import { 
  FileText, ZoomIn, ZoomOut, Maximize, Target, Trash2, Link as LinkIcon, 
  CheckCircle2, AlertTriangle, FileWarning, Plus, ArrowRight, ArrowLeft 
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import DistributorConfidenceBadge from "../components/DistributorConfidenceBadge";

const FIELD_LABELS = {
  qty: "Qty", free_qty: "Free", mrp: "MRP", rate: "Rate",
  discount_pct: "Disc %", special_discount_pct: "Sp. Disc %", gst_pct: "GST %",
};
const EDITABLE_FIELDS = Object.keys(FIELD_LABELS);

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

const PICKER_PAGE_SIZE = 8;

function MedicineLinkPicker({ onLink }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    setPage(1);
    setResults([]);
    setHasMore(false);
  }, [query]);

  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([]);
      setHasMore(false);
      return;
    }
    setSearching(true);
    const t = setTimeout(() => {
      api.browseMedicines({ q: query, page, page_size: PICKER_PAGE_SIZE })
        .then((d) => {
          if (page === 1) {
            setResults(d.items);
          } else {
            setResults((prev) => [...prev, ...d.items]);
          }
          setHasMore(d.items.length === PICKER_PAGE_SIZE);
        })
        .finally(() => setSearching(false));
    }, 250);
    return () => clearTimeout(t);
  }, [query, page]);

  function handleLoadMore() {
    setPage((p) => p + 1);
  }

  return (
    <div style={{ marginTop: "var(--space-2)", background: "var(--bg-app)", padding: "var(--space-2)", borderRadius: "var(--radius-md)", border: "1px solid var(--border-subtle)" }}>
      <input
        className="input"
        style={{ width: "100%", fontSize: "var(--text-xs)", padding: "var(--space-2)" }}
        placeholder="Type to search master list and link..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      {searching && <p style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)", margin: "4px 0 0" }}>Searching directory...</p>}
      {results.length > 0 && (
        <div style={{ marginTop: "var(--space-2)" }}>
          <div className="table-container" style={{ borderRadius: "var(--radius-sm)" }}>
            <table className="table" style={{ fontSize: "var(--text-xs)" }}>
              <tbody>
                {results.map((m) => (
                  <tr
                    key={m.id}
                    style={{ cursor: "pointer" }}
                    onClick={() => { onLink(m); setQuery(""); setResults([]); setPage(1); }}
                  >
                    <td style={{ fontWeight: 500 }}>{m.particulars}</td>
                    <td style={{ color: "var(--text-muted)" }}>{m.unit}</td>
                    <td style={{ textAlign: "right", padding: "4px" }}>
                      <button className="btn btn-ghost" style={{ padding: "4px 8px", fontSize: "var(--text-xs)" }}>
                        <LinkIcon size={12} /> Link
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {hasMore && (
            <button
              className="btn btn-ghost"
              style={{ width: "100%", marginTop: 4, fontSize: "var(--text-xs)" }}
              onClick={handleLoadMore}
              disabled={searching}
            >
              {searching ? "Loading..." : `Load more (${results.length} shown)`}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

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
    <div className="card" style={{ padding: "var(--space-3)", position: "sticky", top: 100 }}>
      <div className="flex-between" style={{ marginBottom: "var(--space-3)" }}>
        <strong style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "var(--text-sm)", color: "var(--text-main)" }}>
          <FileText size={16} /> Original Document
        </strong>
        <div style={{ display: "flex", gap: 4, background: "var(--bg-app)", padding: 4, borderRadius: "var(--radius-md)", border: "1px solid var(--border-subtle)" }}>
          <button className="icon-btn" onClick={() => setZoom((z) => Math.max(0.3, +(z - 0.25).toFixed(2)))}><ZoomOut size={14}/></button>
          <span style={{ fontSize: "var(--text-xs)", alignSelf: "center", minWidth: 40, textAlign: "center", fontWeight: 600 }}>{Math.round(zoom * 100)}%</span>
          <button className="icon-btn" onClick={() => setZoom((z) => Math.min(4, +(z + 0.25).toFixed(2)))}><ZoomIn size={14}/></button>
          <button className="icon-btn" onClick={() => setZoom(1)} title="Reset"><Maximize size={14}/></button>
        </div>
      </div>
      
      <AnimatePresence>
        {pickingField && (
          <motion.div 
            initial={{ opacity: 0, height: 0 }} 
            animate={{ opacity: 1, height: "auto" }} 
            exit={{ opacity: 0, height: 0 }}
            style={{ overflow: "hidden", marginBottom: "var(--space-3)" }}
          >
            <div style={{ background: "var(--warning-bg)", color: "var(--warning-text)", padding: "var(--space-2) var(--space-3)", borderRadius: "var(--radius-md)", fontSize: "var(--text-xs)", border: "1px solid var(--warning-border)", display: "flex", alignItems: "center", gap: 6 }}>
              <Target size={14} /> Drag a box around the value for <strong>{FIELD_LABELS[pickingField.field] || pickingField.field}</strong>.
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div
        ref={containerRef}
        style={{
          overflow: "auto", height: "calc(100vh - 200px)", border: "1px solid var(--border-subtle)", 
          borderRadius: "var(--radius-md)", position: "relative", background: "var(--bg-app)",
          cursor: pickingField ? "crosshair" : panning ? "grabbing" : "grab"
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
          style={{
            width: "100%", display: "block", userSelect: "none",
            transform: `scale(${zoom})`, transformOrigin: "top left",
          }}
        />
        {drag && (
          <div
            style={{
              position: "absolute",
              left: Math.min(drag.startX, drag.curX) - drag.imgRect.left,
              top: Math.min(drag.startY, drag.curY) - drag.imgRect.top,
              width: Math.abs(drag.curX - drag.startX), height: Math.abs(drag.curY - drag.startY),
              border: "2px solid var(--primary-500)", background: "rgba(20, 184, 166, 0.15)", pointerEvents: "none",
            }}
          />
        )}
      </div>
    </div>
  );
}

function ItemCard({ row, applied, onFieldChange, onToggleApply, onPickField, pickingField, onLinkMedicine, onRemove }) {
  const isPicking = (field) => pickingField && pickingField.itemId === row.id && pickingField.field === field;

  return (
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      layout
      className="card" 
      style={{ marginBottom: "var(--space-4)", padding: "var(--space-4)" }}
    >
      <div className="flex-between" style={{ gap: "var(--space-3)", marginBottom: "var(--space-3)" }}>
        <div style={{ flex: 1, display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
          <input
            className="input"
            style={{ fontSize: "var(--text-base)", fontWeight: 600, padding: "var(--space-2) var(--space-3)" }}
            value={row.raw_name || ""}
            placeholder="Medicine name as printed..."
            onChange={(e) => onFieldChange(row.id, "raw_name", e.target.value)}
          />
          <button
            className={`icon-btn ${isPicking("raw_name") ? "" : "btn-ghost"}`}
            style={{ background: isPicking("raw_name") ? "var(--primary-100)" : undefined, color: isPicking("raw_name") ? "var(--primary-600)" : undefined }}
            title="Pick name from image"
            onClick={() => onPickField(row.id, "raw_name")}
          >
            <Target size={16} />
          </button>
        </div>
        <button className="icon-btn btn-ghost" title="Remove" onClick={() => onRemove(row.id)} style={{ color: "var(--danger-text)" }}>
          <Trash2 size={16} />
        </button>
      </div>

      <div style={{ marginBottom: "var(--space-4)" }}>
        {row.medicine_id && row.suggested_medicine_name ? (
          <span className={`badge ${row.match_status}`}>
            {row.match_status === "learned" ? "Learned match: "
              : row.match_status === "auto" ? "Auto-matched: "
              : row.match_status === "manual" ? "Linked: " : ""}
            {row.suggested_medicine_name} ({Math.round(row.match_confidence || 0)}%)
          </span>
        ) : (
          <div>
            <span className="badge unmatched">Unmatched — action required</span>
            <MedicineLinkPicker onLink={(medicine) => onLinkMedicine(row.id, medicine)} />
          </div>
        )}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(100px, 1fr))", gap: "var(--space-3)", marginBottom: "var(--space-4)", background: "var(--bg-app)", padding: "var(--space-3)", borderRadius: "var(--radius-md)", border: "1px solid var(--border-subtle)" }}>
        {EDITABLE_FIELDS.map((f) => (
          <div key={f}>
            <label style={{ display: "block", fontSize: "10px", color: "var(--text-muted)", marginBottom: 4, textTransform: "uppercase", fontWeight: 600 }}>{FIELD_LABELS[f]}</label>
            <div style={{ display: "flex", gap: 4 }}>
              <input
                className="input"
                style={{ padding: "4px 8px", fontSize: "var(--text-sm)" }}
                type="number"
                value={row[f] ?? ""}
                onChange={(e) => onFieldChange(row.id, f, e.target.value)}
              />
              <button
                className={`icon-btn ${isPicking(f) ? "" : "btn-ghost"}`}
                style={{ width: 28, height: 28, background: isPicking(f) ? "var(--primary-100)" : undefined, color: isPicking(f) ? "var(--primary-600)" : undefined }}
                title={`Pick from image`}
                onClick={() => onPickField(row.id, f)}
              >
                <Target size={14} />
              </button>
            </div>
          </div>
        ))}
      </div>

      <div className="flex-between" style={{ paddingTop: "var(--space-3)", borderTop: "1px solid var(--border-subtle)" }}>
        <span style={{ background: "var(--success-bg)", color: "var(--success-text)", padding: "4px 12px", borderRadius: "var(--radius-full)", fontSize: "var(--text-sm)", fontWeight: 600, border: "1px solid var(--success-border)" }}>
          Cost/unit: ₹{computeCostPerUnit(row).toFixed(2)}
        </span>
        <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "var(--text-sm)", color: "var(--text-main)", cursor: row.medicine_id ? "pointer" : "not-allowed", opacity: row.medicine_id ? 1 : 0.6 }}>
          <input
            type="checkbox"
            style={{ width: 16, height: 16, accentColor: "var(--primary-500)" }}
            checked={!!applied}
            disabled={!row.medicine_id}
            onChange={(e) => onToggleApply(row.id, e.target.checked)}
          />
          Update Master List
        </label>
      </div>
    </motion.div>
  );
}

export default function ReviewBill() {
  const { billId } = useParams();
  const [bill, setBill] = useState(null);
  const [invoiceNo, setInvoiceNo] = useState("");
  const [distributorName, setDistributorName] = useState("");
  const [rows, setRows] = useState({});
  const [applyFlags, setApplyFlags] = useState({});
  const [stage, setStage] = useState("reviewing");
  const [changeSummary, setChangeSummary] = useState(null);
  const [error, setError] = useState(null);
  const [is409Error, setIs409Error] = useState(false);
  const [pickingField, setPickingField] = useState(null);
  const [regionLoading, setRegionLoading] = useState(false);

  useEffect(() => {
    api.getBill(billId).then((b) => {
      setBill(b);
      setInvoiceNo(b.invoice_no || "");
      setDistributorName(b.distributor_name || "");
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
    setIs409Error(false);
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
      const summary = await api.confirmBill({
        bill_id: Number(billId),
        items,
        invoice_no: invoiceNo || null,
        distributor_name: distributorName || null,
      });
      setChangeSummary(summary);
      setStage("done");
    } catch (err) {
      if (err.status === 409 || (err.message && err.message.toLowerCase().includes("already confirmed"))) {
        setIs409Error(true);
      } else {
        setIs409Error(false);
      }
      setError(err.message);
      setStage("reviewing");
    }
  }

  if (!bill) return <div className="skeleton" style={{ height: "100vh" }}></div>;

  if (stage === "done" && changeSummary) {
    return (
      <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="card card-raised" style={{ maxWidth: 800, margin: "0 auto", marginTop: "var(--space-10)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: "var(--space-6)", color: "var(--success-text)" }}>
          <CheckCircle2 size={32} />
          <h2 style={{ margin: 0, color: "var(--text-main)" }}>Master List Synchronized</h2>
        </div>
        {changeSummary.length === 0 && <p style={{ color: "var(--text-muted)" }}>No master rate list changes were required.</p>}
        
        {changeSummary.length > 0 && (
          <div className="table-container">
            <table className="table">
              <thead><tr><th>Medicine</th><th>Field Updated</th><th>Old Value</th><th>New Value</th><th>Status</th></tr></thead>
              <tbody>
                {changeSummary.map((c, i) => (
                  <tr key={i}>
                    <td style={{ fontWeight: 500 }}>{c.medicine_name}</td>
                    <td><span className="badge" style={{ background: "var(--bg-app)", border: "1px solid var(--border-subtle)" }}>{c.field === "net_rate" ? "Cost (NET)" : "MRP"}</span></td>
                    <td style={{ color: "var(--text-muted)", textDecoration: "line-through" }}>{c.old_value ?? "—"}</td>
                    <td style={{ color: "var(--success-text)", fontWeight: 600 }}>{c.new_value ?? "—"}</td>
                    <td><span className="badge auto">Applied</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div style={{ marginTop: "var(--space-6)", display: "flex", justifyContent: "flex-end" }}>
          <Link to="/" style={{ textDecoration: "none" }}>
            <button className="btn btn-primary"><ArrowRight size={16} /> View Master List</button>
          </Link>
        </div>
      </motion.div>
    );
  }

  if (stage === "expiry_check") {
    return (
      <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} className="card" style={{ maxWidth: 600, margin: "0 auto", marginTop: "var(--space-10)", borderTop: "4px solid var(--warning-text)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: "var(--space-4)" }}>
          <AlertTriangle size={28} className="text-warning-text" style={{ color: "var(--warning-text)" }} />
          <h2 style={{ margin: 0 }}>Missing Expiry Data</h2>
        </div>
        <p style={{ color: "var(--text-muted)", fontSize: "var(--text-sm)", marginBottom: "var(--space-6)" }}>
          The OCR engine could not reliably read the expiry date for these items. Please enter them manually to ensure the Expiry Tracker can alert you in the future.
        </p>
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", marginBottom: "var(--space-6)" }}>
          {itemsMissingExpiry.map((r) => (
            <div key={r.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "var(--space-3)", background: "var(--bg-app)", borderRadius: "var(--radius-md)", border: "1px solid var(--border-subtle)" }}>
              <div style={{ fontWeight: 500, fontSize: "var(--text-sm)" }}>{r.raw_name}</div>
              <input className="input" style={{ width: 160 }} type="date" onChange={(e) => updateField(r.id, "exp_date", e.target.value)} />
            </div>
          ))}
        </div>
        <div style={{ display: "flex", gap: "var(--space-3)", justifyContent: "flex-end" }}>
          <button className="btn btn-ghost" onClick={() => setStage("reviewing")}><ArrowLeft size={16} /> Back</button>
          <button className="btn btn-primary" onClick={() => setStage("confirming")}>Continue to Confirm</button>
        </div>
      </motion.div>
    );
  }

  if (stage === "confirming") {
    return (
      <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="card" style={{ maxWidth: 500, margin: "0 auto", marginTop: "var(--space-10)" }}>
        <h2 style={{ marginBottom: "var(--space-2)" }}>Commit to Ledger?</h2>
        <p style={{ color: "var(--text-muted)", marginBottom: "var(--space-6)" }}>
          You are about to synchronize <strong>{itemsToApplyCount}</strong> matched items to the master rate list and TrustChain ledger.
        </p>
        <div style={{ display: "flex", gap: "var(--space-3)" }}>
          <button className="btn btn-secondary" style={{ flex: 1 }} onClick={() => setStage("reviewing")}>Cancel</button>
          <button className="btn btn-primary" style={{ flex: 1 }} onClick={handleFinalConfirm}>Confirm & Synchronize</button>
        </div>
      </motion.div>
    );
  }

  if (stage === "applying") {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "50vh", gap: "var(--space-4)" }}>
         <div className="skeleton" style={{ width: 64, height: 64, borderRadius: "50%" }}></div>
         <p style={{ color: "var(--text-muted)", fontWeight: 500 }}>Executing Cryptographic Ledger Commit...</p>
      </div>
    );
  }

  return (
    <div style={{ paddingBottom: "var(--space-10)" }}>
      {/* Header Bar */}
      <div className="card" style={{ marginBottom: "var(--space-6)", padding: "var(--space-4)" }}>
        <div className="flex-between">
          <div>
            <h2 style={{ marginBottom: "var(--space-1)", fontSize: "var(--text-2xl)", display: "flex", alignItems: "center", gap: 8 }}>
              <FileText size={24} color="var(--primary-600)" /> Invoice Digitation Review
            </h2>
            <p style={{ color: "var(--text-muted)", fontSize: "var(--text-sm)", margin: 0 }}>
              Batch: {bill.year}-{String(bill.month).padStart(2, "0")} • Processed on {new Date(bill.uploaded_at).toLocaleDateString()}
            </p>
            
            <div style={{ display: "flex", gap: "var(--space-4)", marginTop: "var(--space-4)", flexWrap: "wrap" }}>
              <div style={{ flex: 1, minWidth: 240 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4 }}>
                  <label style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)", display: "block", fontWeight: 600, textTransform: "uppercase" }}>Distributor Entity</label>
                  {bill.distributor_id && <DistributorConfidenceBadge distributorId={bill.distributor_id} />}
                </div>
                <input
                  className="input"
                  value={distributorName}
                  onChange={(e) => { setDistributorName(e.target.value); setIs409Error(false); }}
                  placeholder="e.g. Apollo Pharma..."
                />
              </div>
              <div style={{ flex: 1, minWidth: 200 }}>
                <label style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)", display: "block", marginBottom: 4, fontWeight: 600, textTransform: "uppercase" }}>Invoice Number</label>
                <input
                  className="input"
                  value={invoiceNo}
                  onChange={(e) => { setInvoiceNo(e.target.value); setIs409Error(false); }}
                  placeholder="e.g. INV-100234..."
                />
              </div>
            </div>
          </div>
          <button className="btn btn-primary" onClick={handleProceedClick} disabled={Object.keys(rows).length === 0} style={{ padding: "var(--space-3) var(--space-6)", alignSelf: "flex-start", fontSize: "var(--text-base)" }}>
            Approve Batch ({itemsToApplyCount}) <ArrowRight size={18} />
          </button>
        </div>

        {bill.status === "needs_attention" && (
          <div style={{ background: "var(--warning-bg)", color: "var(--warning-text)", padding: "var(--space-3)", borderRadius: "var(--radius-md)", fontSize: "var(--text-sm)", marginTop: "var(--space-4)", border: "1px solid var(--warning-border)", display: "flex", alignItems: "flex-start", gap: 8 }}>
            <FileWarning size={18} style={{ flexShrink: 0, marginTop: 2 }} />
            <span><strong>Attention Required:</strong> {bill.needs_attention_reason}</span>
          </div>
        )}
        
        {error && !is409Error && (
          <div style={{ background: "var(--danger-bg)", border: "1px solid var(--danger-border)", color: "var(--danger-text)", padding: "var(--space-3)", borderRadius: "var(--radius-md)", marginTop: "var(--space-4)" }}>
            <strong style={{ fontSize: "var(--text-sm)", display: "flex", alignItems: "center", gap: 6 }}><AlertTriangle size={16} /> Error saving bill</strong>
            <p style={{ margin: "4px 0 0", fontSize: "var(--text-sm)" }}>{error}</p>
          </div>
        )}
        
        {is409Error && (
          <div style={{ background: "var(--danger-bg)", border: "1px solid var(--danger-border)", color: "var(--danger-text)", padding: "var(--space-3)", borderRadius: "var(--radius-md)", marginTop: "var(--space-4)" }}>
            <strong style={{ fontSize: "var(--text-sm)", display: "flex", alignItems: "center", gap: 6 }}><AlertTriangle size={16} /> Duplicate Conflict Detected</strong>
            <p style={{ margin: "4px 0 0", fontSize: "var(--text-sm)" }}>{error}</p>
            <p style={{ margin: "4px 0 0", fontSize: "var(--text-xs)", opacity: 0.9 }}>
              This invoice number and distributor match an already-confirmed bill. Modify the metadata above to proceed.
            </p>
          </div>
        )}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(400px, 1fr) minmax(500px, 1.2fr)", gap: "var(--space-6)", alignItems: "start" }}>
        {/* Left Side: Viewer */}
        <BillImageViewer billId={bill.id} pickingField={pickingField} onRegionSelected={handleRegionSelected} />

        {/* Right Side: Rows */}
        <div>
          <div className="flex-between" style={{ marginBottom: "var(--space-4)", padding: "var(--space-2) var(--space-4)", background: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-lg)" }}>
            <p style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)", margin: 0, display: "flex", alignItems: "center", gap: 6 }}>
              <Target size={14} /> Click the target icon to bound a region on the image for instant OCR read.
            </p>
            <button className="btn btn-secondary" style={{ fontSize: "var(--text-xs)" }} onClick={handleAddItem} disabled={addingItem}>
              {addingItem ? "Adding..." : <><Plus size={14} /> Manual Line Item</>}
            </button>
          </div>

          {Object.keys(rows).length === 0 && (
             <div className="empty-state card">
               <FileWarning size={32} className="empty-state-icon" />
               <p className="empty-state-title">No items extracted</p>
               <p style={{ fontSize: "var(--text-sm)", color: "var(--text-muted)", margin: 0 }}>The vision model could not extract tabular data. Please add items manually.</p>
             </div>
          )}

          <AnimatePresence>
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
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}