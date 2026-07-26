import { useEffect, useRef, useState } from "react";
import { Html5Qrcode } from "html5-qrcode";
import { api } from "../api/client.js";

const SCANNER_ID = "barcode-scanner-region";

export default function BarcodeScan() {
  const scannerRef = useRef(null);
  const [scanning, setScanning] = useState(false);
  const [lastCode, setLastCode] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  // --- Manual link flow, shown when a scanned code isn't recognized ---
  const [linkQuery, setLinkQuery] = useState("");
  const [linkResults, setLinkResults] = useState([]);
  const [linking, setLinking] = useState(false);

  useEffect(() => {
    return () => {
      if (scannerRef.current) {
        scannerRef.current.stop().catch(() => {});
      }
    };
  }, []);

  async function handleScannedCode(code) {
    if (code === lastCode) return; // avoid re-firing on every camera frame while the same code is in view
    setLastCode(code);
    setLoading(true);
    setError(null);
    setLinkResults([]);
    try {
      const res = await api.lookupBarcode(code);
      setResult(res);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function startScanning() {
    setError(null);
    setResult(null);
    setLastCode(null);
    setScanning(true);
    try {
      const scanner = new Html5Qrcode(SCANNER_ID);
      scannerRef.current = scanner;
      await scanner.start(
        { facingMode: "environment" },
        { fps: 10, qrbox: { width: 260, height: 160 } },
        (decodedText) => handleScannedCode(decodedText),
        () => {} // ignore per-frame "not found" noise
      );
    } catch (err) {
      setError("Could not access the camera: " + err.message);
      setScanning(false);
    }
  }

  async function stopScanning() {
    if (scannerRef.current) {
      try { await scannerRef.current.stop(); } catch { /* already stopped */ }
    }
    setScanning(false);
  }

  useEffect(() => {
    if (linkQuery.length < 2) { setLinkResults([]); return; }
    const t = setTimeout(() => {
      api.browseMedicines({ q: linkQuery, page: 1, page_size: 8 }).then((d) => setLinkResults(d.items));
    }, 250);
    return () => clearTimeout(t);
  }, [linkQuery]);

  async function handleLinkMedicine(medicineId) {
    if (!lastCode) return;
    setLinking(true);
    setError(null);
    try {
      await api.assignBarcode(medicineId, lastCode);
      const res = await api.lookupBarcode(lastCode);
      setResult(res);
      setLinkResults([]);
      setLinkQuery("");
    } catch (err) {
      setError(err.message);
    } finally {
      setLinking(false);
    }
  }

  return (
    <div>
      <div className="card">
        <h2 style={{ marginBottom: 4 }}>📷 Barcode / QR Scanner</h2>
        <p style={{ color: "#666", fontSize: 13, marginTop: 0 }}>
          Point your camera at a medicine strip's barcode for an instant stock lookup — no typing needed.
        </p>
        <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
          {!scanning ? (
            <button onClick={startScanning}>Start camera</button>
          ) : (
            <button className="secondary" onClick={stopScanning}>Stop camera</button>
          )}
        </div>
        <div
          id={SCANNER_ID}
          style={{
            width: "100%", maxWidth: 420, borderRadius: 12, overflow: "hidden",
            border: scanning ? "2px solid #2563eb" : "1px solid #eee", minHeight: scanning ? 260 : 0,
            background: "#000",
          }}
        />
        {error && <p style={{ color: "#b91c1c", marginTop: 10 }}>{error}</p>}
        {loading && <p style={{ color: "#666", marginTop: 10 }}>Looking up scanned code...</p>}
      </div>

      {result && result.found && (
        <div className="card" style={{ borderLeft: "4px solid #16a34a", animation: "fadeIn 0.3s ease" }}>
          <h3 style={{ marginTop: 0 }}>✅ {result.medicine.particulars}</h3>
          <div className="stat-row">
            <div className={`stat-box ${result.stock.low_stock_threshold != null && result.stock.current_stock < result.stock.low_stock_threshold ? "warn" : ""}`}>
              <div className="value">{result.stock.current_stock}</div>
              <div className="label">Current stock</div>
            </div>
            <div className="stat-box">
              <div className="value">₹{result.medicine.mrp ?? "—"}</div>
              <div className="label">MRP</div>
            </div>
          </div>
          {result.stock.last_purchase && (
            <div className="last-purchase-card">
              <div className="title">📦 Last arrived</div>
              <div>{result.stock.last_purchase.qty_received} units from <strong>{result.stock.last_purchase.distributor_name || "unknown"}</strong></div>
              <div>Rate: ₹{result.stock.last_purchase.rate ?? "—"}</div>
            </div>
          )}
        </div>
      )}

      {result && !result.found && (
        <div className="card" style={{ borderLeft: "4px solid #ea580c", animation: "fadeIn 0.3s ease" }}>
          <h3 style={{ marginTop: 0 }}>🔎 Barcode not recognized yet</h3>
          <p style={{ color: "#666", fontSize: 13 }}>
            This code (<code>{lastCode}</code>) isn't linked to any medicine yet. Search and select the
            correct one below to link it — future scans will resolve instantly.
          </p>
          <input
            style={{ width: "100%" }}
            placeholder="Search medicine name..."
            value={linkQuery}
            onChange={(e) => setLinkQuery(e.target.value)}
          />
          {linkResults.length > 0 && (
            <table style={{ marginTop: 8 }}>
              <tbody>
                {linkResults.map((m) => (
                  <tr key={m.id} style={{ cursor: "pointer" }} onClick={() => handleLinkMedicine(m.id)}>
                    <td>{m.particulars}</td>
                    <td style={{ color: "#888" }}>{m.unit}</td>
                    <td>{linking ? "Linking..." : <button className="secondary">Link this</button>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
      <style>{`@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }`}</style>
    </div>
  );
}