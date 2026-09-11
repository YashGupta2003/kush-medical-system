import { useState, useRef, useCallback, useEffect, forwardRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  FileText, Upload, User, CheckCircle, AlertTriangle,
  RefreshCw, ShoppingCart, Clock, X,
  Stethoscope, Pill, Check, XCircle, AlertCircle, Zap
} from "lucide-react";
import { api } from "../api/client.js";
import { useNavigate } from "react-router-dom";

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────
function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}
function minutesAgo(iso) {
  if (!iso) return null;
  const diff = Math.floor((Date.now() - new Date(iso)) / 60000);
  if (diff < 1) return "just now";
  if (diff < 60) return `${diff}m ago`;
  return `${Math.floor(diff / 60)}h ${diff % 60}m ago`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Status badge
// ─────────────────────────────────────────────────────────────────────────────
const STATUS_META = {
  queued:     { color: "var(--text-muted)",   bg: "var(--bg-surface)",         label: "Queued",     icon: <Clock size={11} /> },
  processing: { color: "var(--warning)",      bg: "rgba(202,138,4,0.1)",       label: "Processing", icon: <RefreshCw size={11} className="spin" /> },
  ready:      { color: "var(--success-text)", bg: "var(--success-bg)",         label: "Ready",      icon: <CheckCircle size={11} /> },
  converted:  { color: "var(--primary-600)",  bg: "var(--primary-50)",         label: "Sold",       icon: <ShoppingCart size={11} /> },
  abandoned:  { color: "var(--danger)",       bg: "rgba(220,38,38,0.08)",      label: "Dismissed",  icon: <XCircle size={11} /> },
};

function StatusBadge({ status }) {
  const meta = STATUS_META[status] || STATUS_META.queued;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      padding: "3px 9px", borderRadius: "var(--radius-full)",
      fontSize: "11px", fontWeight: 700, letterSpacing: "0.03em",
      background: meta.bg, color: meta.color,
    }}>
      {meta.icon} {meta.label}
    </span>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Stock badge
// ─────────────────────────────────────────────────────────────────────────────
function StockBadge({ inStock, qty }) {
  if (inStock === null || inStock === undefined)
    return <span style={{ color: "var(--text-muted)", fontSize: 12 }}>—</span>;
  return inStock ? (
    <span style={{ color: "var(--success-text)", fontSize: 12, fontWeight: 600 }}>
      <Check size={11} style={{ verticalAlign: "middle" }} /> {qty != null ? `${qty} in stock` : "In stock"}
    </span>
  ) : (
    <span style={{ color: "var(--danger)", fontSize: 12, fontWeight: 600 }}>
      <AlertCircle size={11} style={{ verticalAlign: "middle" }} /> Out of stock
    </span>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Toast notification
// ─────────────────────────────────────────────────────────────────────────────
function Toast({ message, type = "success", onClose }) {
  useEffect(() => {
    const t = setTimeout(onClose, 4500);
    return () => clearTimeout(t);
  }, [onClose]);

  const colors = {
    success: { bg: "var(--success-bg)", border: "var(--success-text)", color: "var(--success-text)", icon: <CheckCircle size={16} /> },
    error:   { bg: "rgba(220,38,38,0.08)", border: "var(--danger)", color: "var(--danger)", icon: <AlertCircle size={16} /> },
  };
  const c = colors[type] || colors.success;

  return (
    <motion.div
      initial={{ opacity: 0, y: -16, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -16, scale: 0.95 }}
      style={{
        position: "fixed", top: 80, right: 24, zIndex: 99999,
        background: c.bg, border: `1px solid ${c.border}`, color: c.color,
        borderRadius: "var(--radius-lg)", padding: "12px 18px",
        display: "flex", alignItems: "center", gap: 10,
        fontWeight: 600, fontSize: "var(--text-sm)",
        boxShadow: "0 8px 32px rgba(0,0,0,0.12)",
        maxWidth: 400,
      }}
    >
      {c.icon}
      <span style={{ flex: 1 }}>{message}</span>
      <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: c.color, display: "flex", padding: 2 }}>
        <X size={14} />
      </button>
    </motion.div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Upload panel (left column, sticky)
// ─────────────────────────────────────────────────────────────────────────────
function UploadPanel({ onUploaded }) {
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [phone, setPhone] = useState("");
  const [patientName, setPatientName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const fileRef = useRef();

  const handleFile = (f) => {
    if (!f) return;
    if (!f.type.startsWith("image/")) { setError("Please upload an image file (JPG, PNG, etc.)"); return; }
    setFile(f);
    setError("");
    const reader = new FileReader();
    reader.onload = (e) => setPreview(e.target.result);
    reader.readAsDataURL(f);
  };

  const onDrop = (e) => {
    e.preventDefault(); setDragging(false);
    handleFile(e.dataTransfer.files[0]);
  };

  const clearFile = () => { setFile(null); setPreview(null); };

  const submit = async () => {
    if (!file) { setError("Please select a prescription image"); return; }
    setLoading(true); setError("");
    try {
      const formData = new FormData();
      formData.append("file", file);
      if (phone.trim()) formData.append("customer_phone", phone.trim());
      if (patientName.trim()) formData.append("customer_name", patientName.trim());
      const result = await api.uploadPrescription(formData);
      setFile(null); setPreview(null); setPhone(""); setPatientName("");
      onUploaded(result);
    } catch (e) {
      setError(e.message || "Upload failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      background: "var(--bg-card)", border: "1px solid var(--border-subtle)",
      borderRadius: "var(--radius-lg)", overflow: "hidden",
      boxShadow: "0 2px 16px rgba(0,0,0,0.05)",
      position: "sticky", top: 80,
    }}>
      {/* Gradient header */}
      <div style={{
        background: "linear-gradient(135deg, var(--primary-500), var(--primary-700))",
        padding: "18px 20px", color: "#fff",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Stethoscope size={20} />
          <div>
            <div style={{ fontWeight: 700, fontSize: "var(--text-base)" }}>Scan Prescription</div>
            <div style={{ fontSize: 12, opacity: 0.85, marginTop: 2 }}>Upload photo → AI matches every drug</div>
          </div>
        </div>
      </div>

      <div style={{ padding: 20 }}>
        {/* Drop zone / image preview */}
        {preview ? (
          <div style={{ position: "relative", marginBottom: 14 }}>
            <img
              src={preview} alt="Prescription preview"
              style={{ width: "100%", borderRadius: "var(--radius-md)", maxHeight: 200, objectFit: "cover", display: "block" }}
            />
            <button
              onClick={clearFile}
              style={{
                position: "absolute", top: 6, right: 6,
                background: "rgba(0,0,0,0.6)", color: "#fff",
                border: "none", borderRadius: "50%", width: 26, height: 26,
                cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
              }}
            >
              <X size={14} />
            </button>
            <div style={{ marginTop: 6, fontSize: 12, color: "var(--text-muted)", textAlign: "center" }}>
              {file?.name} · {(file?.size / 1024).toFixed(1)} KB
            </div>
          </div>
        ) : (
          <div
            onClick={() => fileRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            style={{
              border: `2px dashed ${dragging ? "var(--primary-400)" : "var(--border-subtle)"}`,
              borderRadius: "var(--radius-md)", padding: "28px 12px",
              textAlign: "center", cursor: "pointer", transition: "all 0.2s",
              background: dragging ? "var(--primary-50)" : "var(--bg-surface)",
              marginBottom: 14,
            }}
          >
            <input ref={fileRef} type="file" accept="image/*" capture="environment"
              style={{ display: "none" }} onChange={(e) => handleFile(e.target.files[0])} />
            <Upload size={26} style={{ color: "var(--primary-400)", marginBottom: 8 }} />
            <div style={{ fontWeight: 600, color: "var(--text-main)", fontSize: "var(--text-sm)", marginBottom: 3 }}>
              Drop prescription here
            </div>
            <div style={{ fontSize: 12, color: "var(--text-muted)" }}>or tap to browse · JPG, PNG, HEIC</div>
          </div>
        )}

        {/* Patient info */}
        <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 14 }}>
          <div>
            <label style={{ display: "block", fontSize: 11, fontWeight: 700, color: "var(--text-muted)", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.05em" }}>Patient Phone</label>
            <input
              value={phone} onChange={(e) => setPhone(e.target.value)}
              placeholder="Optional — for adherence tracking"
              style={{ width: "100%", padding: "8px 12px", borderRadius: "var(--radius-md)", border: "1px solid var(--border)", background: "var(--bg-surface)", color: "var(--text-main)", fontSize: "var(--text-sm)", boxSizing: "border-box" }}
            />
          </div>
          <div>
            <label style={{ display: "block", fontSize: 11, fontWeight: 700, color: "var(--text-muted)", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.05em" }}>Patient Name</label>
            <input
              value={patientName} onChange={(e) => setPatientName(e.target.value)}
              placeholder="Optional"
              style={{ width: "100%", padding: "8px 12px", borderRadius: "var(--radius-md)", border: "1px solid var(--border)", background: "var(--bg-surface)", color: "var(--text-main)", fontSize: "var(--text-sm)", boxSizing: "border-box" }}
            />
          </div>
        </div>

        {error && (
          <div style={{ background: "rgba(220,38,38,0.08)", border: "1px solid rgba(220,38,38,0.2)", borderRadius: "var(--radius-md)", padding: "9px 13px", color: "var(--danger)", fontSize: 13, marginBottom: 12, display: "flex", alignItems: "center", gap: 6 }}>
            <AlertTriangle size={13} /> {error}
          </div>
        )}

        <motion.button
          whileHover={{ scale: file && !loading ? 1.02 : 1 }}
          whileTap={{ scale: file && !loading ? 0.97 : 1 }}
          onClick={submit}
          disabled={loading || !file}
          style={{
            width: "100%", padding: "11px", borderRadius: "var(--radius-md)", border: "none",
            cursor: loading || !file ? "not-allowed" : "pointer",
            background: loading || !file ? "var(--bg-surface)" : "linear-gradient(135deg, var(--primary-500), var(--primary-700))",
            color: loading || !file ? "var(--text-muted)" : "#fff",
            fontWeight: 700, fontSize: "var(--text-sm)",
            display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
            transition: "all 0.2s",
          }}
        >
          {loading
            ? <><RefreshCw size={15} className="spin" /> Scanning &amp; Matching…</>
            : <><Zap size={15} /> Scan &amp; Match Drugs</>
          }
        </motion.button>

        {/* Tips */}
        <div style={{ marginTop: 14, padding: "10px 12px", background: "var(--bg-surface)", borderRadius: "var(--radius-md)", fontSize: 12, color: "var(--text-muted)", lineHeight: 1.7 }}>
          💡 <strong>Tips for best results</strong><br />
          · Flat, well-lit, no glare or blur<br />
          · Keep all drug names in frame
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Skeleton loader
// ─────────────────────────────────────────────────────────────────────────────
function SkeletonCard() {
  return (
    <div style={{ background: "var(--bg-card)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-lg)", padding: 18, marginBottom: 14 }}>
      <div style={{ display: "flex", gap: 10, marginBottom: 12 }}>
        <div className="skeleton" style={{ width: 68, height: 22, borderRadius: "var(--radius-full)" }} />
        <div className="skeleton" style={{ width: 46, height: 22, borderRadius: "var(--radius-full)" }} />
      </div>
      {[90, 75, 85].map((w, i) => (
        <div key={i} style={{ display: "flex", gap: 10, marginBottom: 8 }}>
          <div className="skeleton" style={{ width: `${w}%`, height: 36, borderRadius: "var(--radius-md)" }} />
          <div className="skeleton" style={{ width: 70, height: 36, borderRadius: "var(--radius-md)", flexShrink: 0 }} />
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Inline Medicine Search (for manual linking/adding)
// ─────────────────────────────────────────────────────────────────────────────
function InlineMedicineSearch({ onSelect, onCancel, placeholder = "Search medicine..." }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    if (query.trim().length < 2) { setResults([]); setSearching(false); return; }
    setSearching(true);
    const t = setTimeout(() => {
      api.browseMedicines({ q: query, page: 1, page_size: 5 }).then((d) =>
        setResults(d.items || [])
      ).finally(() => setSearching(false));
    }, 250);
    return () => clearTimeout(t);
  }, [query]);

  return (
    <div style={{ position: "relative", flex: 1 }}>
      <div style={{ display: "flex", gap: 6 }}>
        <input
          autoFocus
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={placeholder}
          style={{
            flex: 1, padding: "6px 10px", fontSize: 13,
            border: "1px solid var(--primary-400)", borderRadius: "var(--radius-md)",
            background: "var(--bg-surface)", color: "var(--text-main)",
            outline: "none", boxShadow: "0 0 0 2px var(--primary-50)"
          }}
        />
        <button onClick={onCancel} style={{ padding: "6px 10px", background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-md)", cursor: "pointer", fontSize: 12 }}>Cancel</button>
      </div>
      
      {results.length > 0 && (
        <div style={{
          position: "absolute", top: "100%", left: 0, right: 0, zIndex: 10,
          background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: "var(--radius-md)",
          boxShadow: "0 4px 12px rgba(0,0,0,0.1)", marginTop: 4, maxHeight: 200, overflowY: "auto"
        }}>
          {results.map((m) => (
            <div
              key={m.id}
              onClick={() => onSelect(m)}
              style={{ padding: "8px 12px", borderBottom: "1px solid var(--border-subtle)", cursor: "pointer", fontSize: 12, display: "flex", justifyContent: "space-between", alignItems: "center" }}
            >
              <div>
                <div style={{ fontWeight: 600, color: "var(--text-main)" }}>{m.particulars}</div>
                <div style={{ color: "var(--text-muted)", fontSize: 11 }}>{m.unit || "—"}</div>
              </div>
              <span style={{ color: m.current_stock > 0 ? "var(--success-text)" : "var(--danger)", fontWeight: 600, fontSize: 11 }}>
                {m.current_stock > 0 ? `${m.current_stock} in stock` : "OOS"}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Prescription card
// ─────────────────────────────────────────────────────────────────────────────
const PrescriptionCard = forwardRef(({ prescription, isNew, onAddAllToCart, onAbandon }, ref) => {
  const navigate = useNavigate();
  const [addingToCart, setAddingToCart] = useState(false);
  const [removed, setRemoved] = useState(false);
  const [localItems, setLocalItems] = useState(prescription.items || []);
  const [editingItemId, setEditingItemId] = useState(null);
  const [isAddingNew, setIsAddingNew] = useState(false);
  const internalRef = useRef(null);

  useEffect(() => {
    setLocalItems(prescription.items || []);
  }, [prescription.items]);

  // Merge the forwarded ref from Framer Motion with our internal ref
  const setRefs = useCallback(
    (node) => {
      internalRef.current = node;
      if (typeof ref === "function") {
        ref(node);
      } else if (ref) {
        ref.current = node;
      }
    },
    [ref]
  );

  useEffect(() => {
    if (isNew && internalRef.current) {
      internalRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [isNew]);

  const readyItems = localItems.filter(i => i.medicine_id && i.in_stock !== false);
  const oosItems = localItems.filter(i => i.medicine_id && i.in_stock === false);
  const unmatchedItems = localItems.filter(i => !i.medicine_id);
  const substituteItems = oosItems.filter(i => i.substitute_medicine_id);
  const sendableCount = readyItems.length + substituteItems.length;

  const handleLinkItem = async (itemId, medicine) => {
    try {
      const updated = await api.linkPrescriptionItemMedicine(prescription.id, itemId, medicine.id);
      setLocalItems(prev => prev.map(i => i.id === itemId ? updated : i));
      setEditingItemId(null);
    } catch (e) {
      alert(e.message || "Failed to link medicine");
    }
  };

  const handleAddManualItem = async (medicine) => {
    try {
      const newItem = await api.addPrescriptionItem(prescription.id, { medicine_id: medicine.id });
      setLocalItems(prev => [...prev, newItem]);
      setIsAddingNew(false);
    } catch (e) {
      alert(e.message || "Failed to add medicine");
    }
  };

  const handleAddAllToCart = async () => {
    setAddingToCart(true);
    try {
      const cartItems = [
        ...readyItems.map(item => ({ medicine_id: item.medicine_id, qty_sold: item.qty_prescribed || 1 })),
        ...substituteItems.map(item => ({ medicine_id: item.substitute_medicine_id, qty_sold: item.qty_prescribed || 1 })),
      ];

      for (const item of [...readyItems, ...substituteItems]) {
        try { await api.markPrescriptionItemAddedToCart(prescription.id, item.id); } catch (_) {}
      }
      await api.convertPrescription(prescription.id);

      navigate("/pos", {
        state: {
          prefillCart: cartItems, // This might be empty, which is totally fine
          prescriptionId: prescription.id,
          customerId: prescription.customer_id,
          customerPhone: prescription.customer_phone,
          customerName: prescription.customer_name,
        },
      });
      if (onAddAllToCart) onAddAllToCart(prescription.id);
    } catch (e) {
      alert(e.message || "Failed to send to POS");
    } finally {
      setAddingToCart(false);
    }
  };

  const [showConfirmDismiss, setShowConfirmDismiss] = useState(false);

  const handleAbandon = async () => {
    try {
      await api.abandonPrescription(prescription.id);
      setRemoved(true);
      setTimeout(() => onAbandon && onAbandon(prescription.id), 320);
    } catch (e) { alert(e.message || "Failed to dismiss"); }
  };

  return (
    <motion.div
      ref={setRefs}
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: removed ? 0 : 1, y: removed ? -6 : 0, scale: removed ? 0.97 : 1 }}
      exit={{ opacity: 0, scale: 0.97 }}
      transition={{ duration: 0.22 }}
      style={{
        background: "var(--bg-card)",
        border: `1.5px solid ${isNew ? "var(--primary-400)" : "var(--border-subtle)"}`,
        borderRadius: "var(--radius-lg)", padding: 18, marginBottom: 14,
        boxShadow: isNew ? "0 0 0 3px var(--primary-50), 0 2px 12px rgba(0,0,0,0.05)" : "0 2px 10px rgba(0,0,0,0.04)",
        transition: "border-color 0.6s, box-shadow 0.6s",
      }}
    >
      {/* Card header */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 10, marginBottom: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap", marginBottom: 5 }}>
            <StatusBadge status={prescription.status} />
            {isNew && (
              <span style={{ fontSize: 10, fontWeight: 800, letterSpacing: "0.08em", color: "var(--primary-600)", background: "var(--primary-50)", borderRadius: "var(--radius-full)", padding: "2px 8px" }}>
                NEW
              </span>
            )}
            {prescription.ocr_confidence != null && (
              <span style={{ fontSize: 11, color: "var(--text-muted)", background: "var(--bg-surface)", borderRadius: "var(--radius-full)", padding: "2px 7px" }}>
                OCR {prescription.ocr_confidence.toFixed(0)}%
              </span>
            )}
          </div>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
            {prescription.doctor_name && (
              <span style={{ fontSize: 12, color: "var(--text-muted)", display: "flex", alignItems: "center", gap: 3 }}>
                <Stethoscope size={11} /> {prescription.doctor_name}
              </span>
            )}
            {(prescription.customer_name || prescription.customer_phone) && (
              <span style={{ fontSize: 12, color: "var(--primary-600)", fontWeight: 600, display: "flex", alignItems: "center", gap: 3 }}>
                <User size={11} /> {prescription.customer_name || prescription.customer_phone}
              </span>
            )}
            <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
              {formatDate(prescription.created_at)} · {minutesAgo(prescription.created_at)}
            </span>
          </div>
        </div>

        {prescription.status === "ready" && (
          <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
            {showConfirmDismiss ? (
              <>
                <button
                  onClick={() => setShowConfirmDismiss(false)}
                  style={{ padding: "7px 10px", borderRadius: "var(--radius-md)", border: "1px solid var(--border)", background: "transparent", color: "var(--text-muted)", cursor: "pointer", fontSize: 12, fontWeight: 600 }}
                >
                  Cancel
                </button>
                <button
                  onClick={handleAbandon}
                  style={{ padding: "7px 10px", borderRadius: "var(--radius-md)", border: "none", background: "var(--danger)", color: "#fff", cursor: "pointer", fontSize: 12, fontWeight: 600 }}
                >
                  Confirm Dismiss
                </button>
              </>
            ) : (
              <motion.button
                whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.96 }}
                onClick={() => setShowConfirmDismiss(true)}
                title="Dismiss without sale"
                style={{ padding: "7px 10px", borderRadius: "var(--radius-md)", border: "1px solid var(--border)", background: "transparent", color: "var(--text-muted)", cursor: "pointer", fontSize: 12, fontWeight: 600, display: "flex", alignItems: "center", gap: 4 }}
              >
                <X size={12} /> Dismiss
              </motion.button>
            )}
            <motion.button
              whileHover={{ scale: (addingToCart || sendableCount === 0) ? 1 : 1.04 }}
              whileTap={{ scale: (addingToCart || sendableCount === 0) ? 1 : 0.96 }}
              onClick={handleAddAllToCart}
              disabled={addingToCart || sendableCount === 0}
              style={{
                padding: "7px 14px", borderRadius: "var(--radius-md)", border: "none",
                cursor: (addingToCart || sendableCount === 0) ? "not-allowed" : "pointer",
                background: (addingToCart || sendableCount === 0) ? "var(--bg-muted)" : "linear-gradient(135deg, var(--primary-500), var(--primary-700))",
                color: (addingToCart || sendableCount === 0) ? "var(--text-muted)" : "#fff",
                fontSize: 12, fontWeight: 700, display: "flex", alignItems: "center", gap: 5,
                boxShadow: (addingToCart || sendableCount === 0) ? "none" : "0 2px 8px rgba(20,184,166,0.25)",
              }}
            >
              {addingToCart ? <RefreshCw size={12} className="spin" /> : <ShoppingCart size={12} />}
              {addingToCart ? "Sending…" : `Send to POS${sendableCount > 0 ? ` (${sendableCount})` : " (Empty)"}`}
            </motion.button>
          </div>
        )}

        {prescription.status === "converted" && (
          <span style={{ fontSize: 12, color: "var(--primary-600)", fontWeight: 700, display: "flex", alignItems: "center", gap: 4 }}>
            <ShoppingCart size={13} /> Sold
          </span>
        )}
      </div>

      {/* Warning banner */}
      {prescription.processing_error && (
        <div style={{ background: "rgba(202,138,4,0.08)", border: "1px solid rgba(202,138,4,0.2)", borderRadius: "var(--radius-md)", padding: "8px 11px", fontSize: 12, color: "var(--warning)", marginBottom: 10, display: "flex", alignItems: "flex-start", gap: 6 }}>
          <AlertTriangle size={12} style={{ marginTop: 1, flexShrink: 0 }} />
          <span>{prescription.processing_error}</span>
        </div>
      )}

      {/* Drug lines */}
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {localItems.map((item) => {
          const isOos = item.medicine_id && item.in_stock === false;
          const hasSubstitute = isOos && item.substitute_medicine_id;
          const isUnmatched = !item.medicine_id;
          
          if (editingItemId === item.id) {
            return (
              <InlineMedicineSearch 
                key={`edit-${item.id}`} 
                onSelect={(m) => handleLinkItem(item.id, m)} 
                onCancel={() => setEditingItemId(null)} 
                placeholder={`Search to replace "${item.raw_name}"...`}
              />
            );
          }

          return (
            <div
              key={item.id}
              style={{
                display: "grid", gridTemplateColumns: "1fr auto",
                gap: 10, alignItems: "center",
                padding: "9px 11px", borderRadius: "var(--radius-md)",
                background: isOos && !hasSubstitute ? "rgba(220,38,38,0.04)" : isUnmatched ? "var(--bg-surface)" : "rgba(16,185,129,0.04)",
                border: `1px solid ${isOos && !hasSubstitute ? "rgba(220,38,38,0.15)" : isUnmatched ? "var(--border-subtle)" : "rgba(16,185,129,0.15)"}`,
              }}
            >
              <div style={{ minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <div style={{ fontWeight: 600, fontSize: 13, color: "var(--text-main)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {item.added_to_cart && <Check size={11} style={{ color: "var(--success-text)", verticalAlign: "middle", marginRight: 3 }} />}
                    {item.medicine_name || item.raw_name}
                  </div>
                  {prescription.status === "ready" && (
                    <button onClick={() => setEditingItemId(item.id)} style={{ background: "none", border: "none", color: "var(--primary-600)", fontSize: 11, cursor: "pointer", padding: 0 }}>
                      (Edit)
                    </button>
                  )}
                </div>
                {item.medicine_name && item.medicine_name !== item.raw_name && (
                  <div style={{ fontSize: 11, color: "var(--text-muted)" }}>OCR: "{item.raw_name}"</div>
                )}
                {item.dosage_instructions && (
                  <div style={{ fontSize: 11, color: "var(--primary-600)", marginTop: 1 }}>📋 {item.dosage_instructions}</div>
                )}
                {isUnmatched && (
                  <div style={{ fontSize: 11, color: "var(--warning)", marginTop: 1, display: "flex", alignItems: "center", gap: 3 }}>
                    <AlertTriangle size={10} /> No match
                  </div>
                )}
                {hasSubstitute && (
                  <div style={{ fontSize: 11, color: "var(--primary-600)", marginTop: 1, display: "flex", alignItems: "center", gap: 3 }}>
                    <RefreshCw size={10} /> Sub: {item.substitute_medicine_name}
                  </div>
                )}
              </div>
              <div style={{ textAlign: "right", flexShrink: 0 }}>
                {item.qty_prescribed != null && (
                  <div style={{ fontWeight: 700, fontSize: 13, color: "var(--text-main)" }}>×{item.qty_prescribed}</div>
                )}
                <StockBadge inStock={item.in_stock} qty={item.current_stock_qty} />
              </div>
            </div>
          );
        })}

        {/* Add new manual drug line */}
        {prescription.status === "ready" && (
          isAddingNew ? (
            <InlineMedicineSearch 
              onSelect={handleAddManualItem} 
              onCancel={() => setIsAddingNew(false)} 
              placeholder="Search to add missed drug..."
            />
          ) : (
            <button
              onClick={() => setIsAddingNew(true)}
              style={{
                background: "var(--bg-surface)", border: "1px dashed var(--border)",
                color: "var(--text-muted)", borderRadius: "var(--radius-md)",
                padding: "8px", fontSize: 12, fontWeight: 600, cursor: "pointer",
                display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
                marginTop: 2
              }}
            >
              + Add missed drug manually
            </button>
          )
        )}
        
        {localItems.length === 0 && !isAddingNew && (
           <div style={{ textAlign: "center", color: "var(--text-muted)", padding: "14px 0", fontSize: 13 }}>
             <Pill size={22} style={{ opacity: 0.3, marginBottom: 6, display: "block", margin: "0 auto" }} />
             No drugs extracted
           </div>
        )}
      </div>

      {/* Footer summary */}
      {localItems.length > 0 && (
        <div style={{ display: "flex", gap: 14, marginTop: 10, paddingTop: 10, borderTop: "1px solid var(--border-subtle)", fontSize: 11, flexWrap: "wrap" }}>
          {readyItems.length > 0 && <span style={{ color: "var(--success-text)", fontWeight: 700 }}><CheckCircle size={10} style={{ verticalAlign: "middle" }} /> {readyItems.length} in stock</span>}
          {oosItems.length > 0 && <span style={{ color: "var(--danger)", fontWeight: 700 }}><AlertCircle size={10} style={{ verticalAlign: "middle" }} /> {oosItems.length} OOS</span>}
          {unmatchedItems.length > 0 && <span style={{ color: "var(--warning)", fontWeight: 700 }}><AlertTriangle size={10} style={{ verticalAlign: "middle" }} /> {unmatchedItems.length} unmatched</span>}
          {substituteItems.length > 0 && <span style={{ color: "var(--primary-600)", fontWeight: 700 }}><RefreshCw size={10} style={{ verticalAlign: "middle" }} /> {substituteItems.length} substitute{substituteItems.length > 1 ? "s" : ""}</span>}
        </div>
      )}
    </motion.div>
  );
});

// ─────────────────────────────────────────────────────────────────────────────
// Stats strip
// ─────────────────────────────────────────────────────────────────────────────
function StatsStrip({ total, ready, converted, uncollected }) {
  const stats = [
    { label: "Total", value: total, color: "var(--text-main)" },
    { label: "Ready", value: ready, color: "var(--success-text)" },
    { label: "Converted", value: converted, color: "var(--primary-600)" },
    { label: "Uncollected >30m", value: uncollected, color: uncollected > 0 ? "var(--danger)" : "var(--text-muted)" },
  ];
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 10, marginBottom: 20 }}>
      {stats.map(s => (
        <motion.div
          key={s.label}
          initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
          style={{ background: "var(--bg-card)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-lg)", padding: "14px 16px", textAlign: "center" }}
        >
          <div style={{ fontSize: "1.5rem", fontWeight: 800, color: s.color, lineHeight: 1 }}>{s.value}</div>
          <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.04em" }}>{s.label}</div>
        </motion.div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main page
// ─────────────────────────────────────────────────────────────────────────────
export default function Prescriptions() {
  const [prescriptions, setPrescriptions] = useState([]);
  const [total, setTotal] = useState(0);
  const [uncollectedCount, setUncollectedCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState("");
  const [toast, setToast] = useState(null);
  const [newIds, setNewIds] = useState(new Set());

  const readyCount = prescriptions.filter(p => p.status === "ready").length;
  const convertedCount = prescriptions.filter(p => p.status === "converted").length;

  const loadPrescriptions = useCallback(async (statusFilter) => {
    setLoading(true);
    try {
      const [data, uncollected] = await Promise.all([
        api.listPrescriptions({ status: statusFilter || undefined }),
        api.getUncollectedPrescriptions(30),
      ]);
      setPrescriptions(data.items || []);
      setTotal(data.total || 0);
      setUncollectedCount(uncollected.length || 0);
    } catch (e) {
      console.error("Failed to load prescriptions:", e);
      setToast({ message: "Failed to load prescriptions", type: "error" });
    } finally {
      setLoading(false);
    }
  }, []);

  // ✅ FIXED: was useState() — initial data load now works correctly on mount
  useEffect(() => {
    loadPrescriptions("");
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleFilterChange = (value) => {
    setFilterStatus(value);
    loadPrescriptions(value);
  };

  const handleUploaded = (newPrescription) => {
    setPrescriptions(prev => [newPrescription, ...prev]);
    setTotal(prev => prev + 1);
    setNewIds(prev => new Set([...prev, newPrescription.id]));
    setTimeout(() => {
      setNewIds(prev => { const next = new Set(prev); next.delete(newPrescription.id); return next; });
    }, 8000);
    const itemCount = newPrescription.items?.length || 0;
    const matched = newPrescription.items?.filter(i => i.medicine_id).length || 0;
    setToast({
      message: `Scanned! ${matched}/${itemCount} drug${itemCount !== 1 ? "s" : ""} matched — tap "Send to POS" to complete the sale.`,
      type: "success",
    });
  };

  const handleAbandon = (id) => {
    setPrescriptions(prev => prev.filter(p => p.id !== id));
    setTotal(prev => Math.max(0, prev - 1));
  };

  const handleConvert = (id) => {
    setPrescriptions(prev => prev.map(p =>
      p.id === id ? { ...p, status: "converted", converted_to_sale: true } : p
    ));
  };

  const STATUS_FILTERS = [
    { label: "All", value: "" },
    { label: "Ready", value: "ready" },
    { label: "Sold", value: "converted" },
    { label: "Dismissed", value: "abandoned" },
  ];

  return (
    <div style={{ width: "100%" }}>
      {/* Toast */}
      <AnimatePresence>
        {toast && <Toast key="toast" message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
      </AnimatePresence>

      {/* Hero header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
        style={{
          background: "linear-gradient(135deg, var(--primary-600) 0%, var(--primary-800) 100%)",
          borderRadius: "var(--radius-xl)", padding: "22px 28px", marginBottom: 22,
          display: "flex", alignItems: "center", justifyContent: "space-between",
          boxShadow: "0 4px 24px rgba(20,184,166,0.18)",
        }}
      >
        <div>
          <h1 style={{ margin: 0, fontSize: "1.45rem", fontWeight: 800, color: "#fff", display: "flex", alignItems: "center", gap: 10 }}>
            <Stethoscope size={24} /> Prescription Intelligence
          </h1>
          <p style={{ margin: "4px 0 0", color: "rgba(255,255,255,0.75)", fontSize: 13 }}>
            Scan → AI matches every drug → one tap to POS
          </p>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          {uncollectedCount > 0 && (
            <motion.div
              initial={{ scale: 0.8 }} animate={{ scale: 1 }}
              style={{ background: "rgba(220,38,38,0.85)", color: "#fff", borderRadius: "var(--radius-md)", padding: "7px 13px", fontSize: 13, fontWeight: 700, display: "flex", alignItems: "center", gap: 6 }}
            >
              <AlertCircle size={14} /> {uncollectedCount} uncollected &gt;30m
            </motion.div>
          )}
          <motion.button
            whileHover={{ scale: 1.04, background: "rgba(255,255,255,0.25)" }}
            whileTap={{ scale: 0.96 }}
            onClick={() => loadPrescriptions(filterStatus)}
            style={{ padding: "8px 16px", borderRadius: "var(--radius-full)", border: "1px solid rgba(255,255,255,0.3)", background: "rgba(255,255,255,0.15)", color: "#fff", cursor: "pointer", fontWeight: 600, fontSize: 13, display: "flex", alignItems: "center", gap: 6 }}
          >
            <RefreshCw size={13} /> Refresh
          </motion.button>
        </div>
      </motion.div>

      {/* Stats */}
      <StatsStrip total={total} ready={readyCount} converted={convertedCount} uncollected={uncollectedCount} />

      {/* Two-column layout */}
      <div style={{ display: "grid", gridTemplateColumns: "340px 1fr", gap: 20, alignItems: "start" }}>

        {/* LEFT — Upload (sticky) */}
        <UploadPanel onUploaded={handleUploaded} />

        {/* RIGHT — List */}
        <div>
          {/* Filter tabs */}
          <div style={{ display: "flex", gap: 8, marginBottom: 16, alignItems: "center" }}>
            {STATUS_FILTERS.map(f => (
              <button
                key={f.value}
                onClick={() => handleFilterChange(f.value)}
                style={{
                  padding: "6px 16px", borderRadius: "var(--radius-full)",
                  border: `1px solid ${filterStatus === f.value ? "var(--primary-400)" : "var(--border)"}`,
                  background: filterStatus === f.value ? "var(--primary-50)" : "var(--bg-surface)",
                  color: filterStatus === f.value ? "var(--primary-600)" : "var(--text-muted)",
                  cursor: "pointer", fontWeight: 600, fontSize: 13, transition: "all 0.2s",
                }}
              >
                {f.label}
              </button>
            ))}
            <span style={{ marginLeft: "auto", fontSize: 12, color: "var(--text-muted)" }}>
              {total} total
            </span>
          </div>

          {/* Cards */}
          {loading ? (
            <>{[1, 2, 3].map(i => <SkeletonCard key={i} />)}</>
          ) : prescriptions.length === 0 ? (
            <motion.div
              initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              style={{ textAlign: "center", padding: "56px 20px", color: "var(--text-muted)", background: "var(--bg-card)", borderRadius: "var(--radius-lg)", border: "1px solid var(--border-subtle)" }}
            >
              <FileText size={40} style={{ opacity: 0.2, marginBottom: 14 }} />
              <div style={{ fontWeight: 700, fontSize: "var(--text-base)", color: "var(--text-main)", marginBottom: 6 }}>No prescriptions yet</div>
              <div style={{ fontSize: 13 }}>
                Upload a photo on the left — AI matches every drug<br />and pre-fills the POS cart automatically.
              </div>
            </motion.div>
          ) : (
            <AnimatePresence mode="popLayout">
              {prescriptions.map(p => (
                <PrescriptionCard
                  key={p.id}
                  prescription={p}
                  isNew={newIds.has(p.id)}
                  onAddAllToCart={handleConvert}
                  onAbandon={handleAbandon}
                />
              ))}
            </AnimatePresence>
          )}
        </div>
      </div>
    </div>
  );
}
