import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { AlertTriangle, UploadCloud, FileText, ArrowRight, Loader } from "lucide-react";
import { api } from "../api/client.js";

function usePolledStatus(billId) {
  const [status, setStatus] = useState("queued");
  const [confidence, setConfidence] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!billId) return;
    let cancelled = false;
    let timer;

    async function poll() {
      try {
        const s = await api.getBillStatus(billId);
        if (cancelled) return;
        setStatus(s.status);
        setConfidence(s.ocr_confidence);
        setError(s.processing_error);
        if (s.status === "queued" || s.status === "processing") {
          timer = setTimeout(poll, 2000);
        }
      } catch (e) {
        if (!cancelled) setError(e.message);
      }
    }
    poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [billId]);

  return { status, confidence, error };
}

function BillProgressRow({ billId, filename, duplicateWarning }) {
  const { status, confidence, error } = usePolledStatus(billId);
  const navigate = useNavigate();

  const statusLabel = {
    queued: "Waiting in queue...",
    processing: "Reading bill (OCR running)...",
    pending_review: "Ready to review",
    needs_attention: `Needs attention${confidence != null ? ` (confidence ${Math.round(confidence)}%)` : ""}`,
    failed: `Failed: ${error || "unknown error"}`,
  }[status] || status;

  const badgeClass = {
    pending_review: "auto",
    needs_attention: "manual",
    failed: "unmatched",
  }[status] || "manual";

  return (
    <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} className="card" style={{ display: "flex", flexDirection: "column", gap: "12px", borderLeft: status === "failed" ? "4px solid var(--danger-500)" : status === "pending_review" ? "4px solid var(--success-500)" : status === "needs_attention" ? "4px solid var(--warning-500)" : "4px solid var(--primary-500)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <FileText size={24} color="var(--text-muted)" />
          <div>
            <strong style={{ color: "var(--text-main)", fontSize: "15px" }}>{filename}</strong>
            <div style={{ fontSize: "13px", color: "var(--text-secondary)", marginTop: "4px" }}>
              <span className={`badge ${badgeClass}`}>{statusLabel}</span>
            </div>
          </div>
        </div>
        {(status === "pending_review" || status === "needs_attention") && (
          <button className="btn btn-primary" onClick={() => navigate(`/review/${billId}`)} style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            Review <ArrowRight size={16} />
          </button>
        )}
      </div>
      {duplicateWarning && (
        <div style={{ background: "var(--warning-100)", border: "1px solid var(--warning-300)", color: "var(--warning-700)", padding: "10px 14px", borderRadius: "8px", fontSize: "13px", display: "flex", gap: "8px", alignItems: "center" }}>
          <AlertTriangle size={16} color="var(--warning-600)" style={{ flexShrink: 0 }} />
          <span>{duplicateWarning}</span>
        </div>
      )}
    </motion.div>
  );
}

export default function UploadBill() {
  const [files, setFiles] = useState([]);
  const [distributorName, setDistributorName] = useState("");
  const [invoiceNo, setInvoiceNo] = useState("");
  const [invoiceDate, setInvoiceDate] = useState("");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [uploadedBills, setUploadedBills] = useState([]);
  const fileInputRef = useRef(null);

  async function handleSubmit(e) {
    e.preventDefault();
    if (files.length === 0) return;
    setUploading(true);
    setError(null);

    try {
      if (files.length === 1) {
        const formData = new FormData();
        formData.append("file", files[0]);
        if (distributorName) formData.append("distributor_name", distributorName);
        if (invoiceNo) formData.append("invoice_no", invoiceNo);
        if (invoiceDate) formData.append("invoice_date", invoiceDate);
        const res = await api.uploadBill(formData);
        setUploadedBills(prev => [{ bill_id: res.bill_id, filename: files[0].name, duplicate_warning: res.duplicate_warning }, ...prev]);
      } else {
        const formData = new FormData();
        files.forEach((f) => formData.append("files", f));
        if (distributorName) formData.append("distributor_name", distributorName);
        const res = await api.uploadBillsBatch(formData);
        const newBills = res.map((r, i) => ({ bill_id: r.bill_id, filename: files[i]?.name || `bill ${i + 1}`, duplicate_warning: r.duplicate_warning }));
        setUploadedBills(prev => [...newBills, ...prev]);
      }
      setFiles([]);
      setDistributorName("");
      setInvoiceNo("");
      setInvoiceDate("");
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.2 }}
      className="page-content"
    >
      <div className="card">
        <div style={{ display: "flex", gap: "12px", alignItems: "flex-start", marginBottom: "20px" }}>
          <div style={{ background: "var(--primary-100)", padding: "10px", borderRadius: "10px" }}>
            <UploadCloud size={24} color="var(--primary-600)" />
          </div>
          <div>
            <h2 style={{ margin: "0 0 4px 0", color: "var(--text-main)" }}>Upload purchase bill(s)</h2>
            <p style={{ color: "var(--text-secondary)", fontSize: "13px", margin: 0, lineHeight: 1.5 }}>
              Select one bill, or several at once - each is processed independently in the background.
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: "16px" }}>
            <div style={{ 
              border: "2px dashed var(--border-color)", 
              borderRadius: "12px", 
              padding: "24px", 
              textAlign: "center",
              background: "var(--bg-muted)",
              transition: "border-color 0.2s ease"
            }} 
            onMouseOver={(e) => e.currentTarget.style.borderColor = 'var(--primary-400)'}
            onMouseOut={(e) => e.currentTarget.style.borderColor = 'var(--border-color)'}>
              <UploadCloud size={32} color="var(--text-muted)" style={{ marginBottom: "12px" }} />
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*,application/pdf"
                multiple
                onChange={(e) => setFiles(Array.from(e.target.files))}
                required
                style={{ display: "block", width: "100%", cursor: "pointer" }}
              />
              {files.length > 1 && (
                <p style={{ fontSize: "13px", color: "var(--text-secondary)", marginTop: "12px", fontWeight: 600 }}>
                  <FileText size={14} className="inline mr-1" /> {files.length} files selected
                </p>
              )}
            </div>
          </div>
          <div style={{ display: "flex", gap: "12px", marginBottom: "20px", flexWrap: "wrap" }}>
            <div style={{ flex: 1, minWidth: "200px" }}>
              <label style={{ fontSize: "12px", color: "var(--text-secondary)", marginBottom: "4px", display: "block" }}>Distributor (optional)</label>
              <input
                placeholder="e.g. RATHORE MEDICOS"
                value={distributorName}
                onChange={(e) => setDistributorName(e.target.value)}
                style={{ width: "100%" }}
              />
            </div>
            {files.length <= 1 && (
              <>
                <div style={{ flex: 1, minWidth: "150px" }}>
                  <label style={{ fontSize: "12px", color: "var(--text-secondary)", marginBottom: "4px", display: "block" }}>Invoice no. (optional)</label>
                  <input
                    placeholder="e.g. INV-2023"
                    value={invoiceNo}
                    onChange={(e) => setInvoiceNo(e.target.value)}
                    style={{ width: "100%" }}
                  />
                </div>
                <div style={{ flex: 1, minWidth: "150px" }}>
                  <label style={{ fontSize: "12px", color: "var(--text-secondary)", marginBottom: "4px", display: "block" }}>Invoice date (optional)</label>
                  <input type="date" value={invoiceDate} onChange={(e) => setInvoiceDate(e.target.value)} style={{ width: "100%" }} />
                </div>
              </>
            )}
          </div>
          <button type="submit" className="btn btn-primary" disabled={uploading || files.length === 0} style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "8px", width: "100%", padding: "12px" }}>
            {uploading ? <Loader size={18} className="spin" /> : <UploadCloud size={18} />}
            {uploading ? "Uploading..." : files.length > 1 ? `Upload ${files.length} bills` : "Upload and process"}
          </button>
          {error && <p style={{ color: "var(--danger-600)", marginTop: "16px", fontSize: "14px", textAlign: "center" }}>{error}</p>}
        </form>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        {uploadedBills.map((b, i) => (
          <BillProgressRow key={`${b.bill_id}-${i}`} billId={b.bill_id} filename={b.filename} duplicateWarning={b.duplicate_warning} />
        ))}
      </div>
      <style>{`
        .spin { animation: spin 1s linear infinite; }
        @keyframes spin { 100% { transform: rotate(360deg); } }
      `}</style>
    </motion.div>
  );
}
