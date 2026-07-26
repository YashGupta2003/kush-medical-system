import { useEffect, useState } from "react";
import { api } from "../api/client.js";

const MONTH_NAMES = ["January","February","March","April","May","June","July","August","September","October","November","December"];

export default function GstReport() {
  const today = new Date();
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth() + 1);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState(null);

  function refresh() {
    setLoading(true);
    setError(null);
    api.getGstReport(year, month)
      .then(setReport)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => { refresh(); /* eslint-disable-next-line */ }, [year, month]);

  async function handleDownload() {
    setDownloading(true);
    setError(null);
    try {
      await api.downloadGstReportPdf(year, month);
    } catch (e) {
      setError(e.message);
    } finally {
      setDownloading(false);
    }
  }

  const years = Array.from({ length: 5 }, (_, i) => today.getFullYear() - i);

  return (
    <div>
      <div className="card">
        <div className="flex-between">
          <div>
            <h2 style={{ marginBottom: 4 }}>🧾 GST Purchase Report</h2>
            <p style={{ color: "#666", fontSize: 13, marginTop: 0 }}>
              Slab-wise CGST/SGST breakdown from your confirmed purchase bills — ready for your CA.
            </p>
          </div>
          <button onClick={handleDownload} disabled={downloading || loading}>
            {downloading ? "Preparing PDF..." : "⬇ Download PDF"}
          </button>
        </div>

        <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
          <select value={month} onChange={(e) => setMonth(Number(e.target.value))}>
            {MONTH_NAMES.map((name, i) => <option key={i} value={i + 1}>{name}</option>)}
          </select>
          <select value={year} onChange={(e) => setYear(Number(e.target.value))}>
            {years.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>
        {error && <p style={{ color: "#b91c1c", marginTop: 10 }}>{error}</p>}
      </div>

      {loading && <p>Loading report...</p>}

      {!loading && report && (
        <>
          <div className="stat-row">
            <div className="stat-box"><div className="value">{report.bill_count}</div><div className="label">Confirmed bills</div></div>
            <div className="stat-box"><div className="value">₹{report.grand_taxable_amount.toLocaleString("en-IN")}</div><div className="label">Taxable amount</div></div>
            <div className="stat-box"><div className="value">₹{report.grand_cgst.toLocaleString("en-IN")}</div><div className="label">Total CGST</div></div>
            <div className="stat-box"><div className="value">₹{report.grand_sgst.toLocaleString("en-IN")}</div><div className="label">Total SGST</div></div>
            <div className="stat-box"><div className="value">₹{report.grand_total_amount.toLocaleString("en-IN")}</div><div className="label">Total purchase value</div></div>
          </div>

          <div className="card">
            <h3 style={{ marginTop: 0 }}>Breakdown by GST slab — {report.month_label}</h3>
            {report.slabs.length === 0 ? (
              <p style={{ color: "#888", fontSize: 13 }}>No confirmed bills found for this month.</p>
            ) : (
              <table>
                <thead>
                  <tr><th>GST %</th><th>Items</th><th>Taxable Amt</th><th>CGST</th><th>SGST</th><th>Total Tax</th><th>Total Amt</th></tr>
                </thead>
                <tbody>
                  {report.slabs.map((s) => (
                    <tr key={s.gst_pct}>
                      <td><span className="badge auto">{s.gst_pct}%</span></td>
                      <td>{s.item_count}</td>
                      <td>₹{s.taxable_amount.toLocaleString("en-IN")}</td>
                      <td>₹{s.cgst.toLocaleString("en-IN")}</td>
                      <td>₹{s.sgst.toLocaleString("en-IN")}</td>
                      <td>₹{s.total_tax.toLocaleString("en-IN")}</td>
                      <td><strong>₹{s.total_amount.toLocaleString("en-IN")}</strong></td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr style={{ fontWeight: 700, borderTop: "2px solid #333" }}>
                    <td>TOTAL</td><td>—</td>
                    <td>₹{report.grand_taxable_amount.toLocaleString("en-IN")}</td>
                    <td>₹{report.grand_cgst.toLocaleString("en-IN")}</td>
                    <td>₹{report.grand_sgst.toLocaleString("en-IN")}</td>
                    <td>₹{report.grand_total_tax.toLocaleString("en-IN")}</td>
                    <td>₹{report.grand_total_amount.toLocaleString("en-IN")}</td>
                  </tr>
                </tfoot>
              </table>
            )}
            <p style={{ color: "#999", fontSize: 12, marginTop: 12 }}>
              Note: CGST/SGST assume intra-state purchases split equally. Verify against original invoices
              for any interstate (IGST) transactions before filing.
            </p>
          </div>
        </>
      )}
    </div>
  );
}