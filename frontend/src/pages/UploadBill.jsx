import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client.js";

export default function UploadBill() {
  const [file, setFile] = useState(null);
  const [distributorName, setDistributorName] = useState("");
  const [invoiceNo, setInvoiceNo] = useState("");
  const [invoiceDate, setInvoiceDate] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      if (distributorName) formData.append("distributor_name", distributorName);
      if (invoiceNo) formData.append("invoice_no", invoiceNo);
      if (invoiceDate) formData.append("invoice_date", invoiceDate);

      const bill = await api.uploadBill(formData);
      navigate(`/review/${bill.id}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card">
      <h2>Upload a purchase bill</h2>
      <p style={{ color: "#666", fontSize: 13 }}>
        Take a clear, flat photo of the invoice. The system will read every
        line item, calculate the real per-unit cost, and show you everything
        for confirmation before anything is saved.
      </p>
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: 12 }}>
          <input
            type="file"
            accept="image/*"
            capture="environment"
            onChange={(e) => setFile(e.target.files[0])}
            required
          />
        </div>
        <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
          <input
            placeholder="Distributor name (optional, e.g. Rathore Medicos)"
            value={distributorName}
            onChange={(e) => setDistributorName(e.target.value)}
            style={{ flex: 1, minWidth: 200 }}
          />
          <input
            placeholder="Invoice no. (optional)"
            value={invoiceNo}
            onChange={(e) => setInvoiceNo(e.target.value)}
          />
          <input
            type="date"
            value={invoiceDate}
            onChange={(e) => setInvoiceDate(e.target.value)}
          />
        </div>
        <button type="submit" disabled={loading || !file}>
          {loading ? "Reading bill..." : "Upload and extract"}
        </button>
        {error && <p style={{ color: "#b91c1c", marginTop: 10 }}>{error}</p>}
      </form>
    </div>
  );
}
