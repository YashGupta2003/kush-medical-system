import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
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

function BillProgressRow({ billId, filename }) {
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
    <div className="card" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
      <div>
        <strong>{filename}</strong>
        <div style={{ fontSize: 13, color: "#666" }}>
          <span className={`badge ${badgeClass}`}>{statusLabel}</span>
        </div>
      </div>
      {(status === "pending_review" || status === "needs_attention") && (
        <button onClick={() => navigate(`/review/${billId}`)}>Review</button>
      )}
    </div>
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
        setUploadedBills([{ bill_id: res.bill_id, filename: files[0].name }]);
      } else {
        const formData = new FormData();
        files.forEach((f) => formData.append("files", f));
        if (distributorName) formData.append("distributor_name", distributorName);
        const res = await api.uploadBillsBatch(formData);
        setUploadedBills(res.map((r, i) => ({ bill_id: r.bill_id, filename: files[i]?.name || `bill ${i + 1}` })));
      }
      setFiles([]);
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  }

  return (
    <div>
      <div className="card">
        <h2>Upload purchase bill(s)</h2>
        <p style={{ color: "#666", fontSize: 13 }}>
          Select one bill, or several at once - each is processed independently in the background.
        </p>
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 12 }}>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              capture="environment"
              multiple
              onChange={(e) => setFiles(Array.from(e.target.files))}
              required
            />
            {files.length > 1 && (
              <p style={{ fontSize: 13, color: "#666" }}>{files.length} files selected</p>
            )}
          </div>
          <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
            <input
              placeholder="Distributor name (optional)"
              value={distributorName}
              onChange={(e) => setDistributorName(e.target.value)}
              style={{ flex: 1, minWidth: 200 }}
            />
            {files.length <= 1 && (
              <>
                <input
                  placeholder="Invoice no. (optional)"
                  value={invoiceNo}
                  onChange={(e) => setInvoiceNo(e.target.value)}
                />
                <input type="date" value={invoiceDate} onChange={(e) => setInvoiceDate(e.target.value)} />
              </>
            )}
          </div>
          <button type="submit" disabled={uploading || files.length === 0}>
            {uploading ? "Uploading..." : files.length > 1 ? `Upload ${files.length} bills` : "Upload and process"}
          </button>
          {error && <p style={{ color: "#b91c1c", marginTop: 10 }}>{error}</p>}
        </form>
      </div>

      {uploadedBills.map((b) => (
        <BillProgressRow key={b.bill_id} billId={b.bill_id} filename={b.filename} />
      ))}
    </div>
  );
}
