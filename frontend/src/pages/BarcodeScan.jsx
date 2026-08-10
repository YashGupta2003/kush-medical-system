import { useEffect, useRef, useState } from "react";
import { Html5Qrcode } from "html5-qrcode";
import { motion } from "framer-motion";
import { Camera, CheckCircle, Package, Search as SearchIcon, ScanLine, XCircle } from "lucide-react";
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
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.2 }}
      className="page-content"
    >
      <div className="card">
        <div style={{ display: "flex", alignItems: "flex-start", gap: "12px", marginBottom: "16px" }}>
          <div style={{ background: "var(--primary-100)", padding: "10px", borderRadius: "10px" }}>
            <ScanLine size={24} color="var(--primary-600)" />
          </div>
          <div>
            <h2 style={{ margin: "0 0 4px 0", color: "var(--text-main)" }}>Barcode / QR Scanner</h2>
            <p style={{ color: "var(--text-secondary)", fontSize: "13px", margin: 0, lineHeight: 1.5 }}>
              Point your camera at a medicine strip's barcode for an instant stock lookup — no typing needed.
            </p>
          </div>
        </div>
        
        <div style={{ display: "flex", gap: "8px", marginBottom: "16px" }}>
          {!scanning ? (
            <button className="btn btn-primary" onClick={startScanning} style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <Camera size={16} /> Start camera
            </button>
          ) : (
            <button className="btn secondary" onClick={stopScanning} style={{ display: "flex", alignItems: "center", gap: "8px", background: "var(--bg-muted)" }}>
              <XCircle size={16} /> Stop camera
            </button>
          )}
        </div>
        
        <div
          id={SCANNER_ID}
          style={{
            width: "100%", maxWidth: "420px", borderRadius: "12px", overflow: "hidden",
            border: scanning ? "2px solid var(--primary-500)" : "1px solid var(--border-color)", 
            minHeight: scanning ? "260px" : 0,
            background: "#000",
            transition: "min-height 0.3s ease, border 0.3s ease",
            margin: "0 auto"
          }}
        />
        {error && <p style={{ color: "var(--danger-600)", marginTop: "16px", fontSize: "14px", textAlign: "center" }}>{error}</p>}
        {loading && <p style={{ color: "var(--text-secondary)", marginTop: "16px", fontSize: "14px", textAlign: "center", display: "flex", alignItems: "center", justifyContent: "center", gap: "8px" }}><ScanLine className="spin" size={16}/> Looking up scanned code...</p>}
      </div>

      {result && result.found && (
        <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="card" style={{ borderLeft: "4px solid var(--success-500)" }}>
          <h3 style={{ marginTop: 0, display: "flex", alignItems: "center", gap: "8px", color: "var(--text-main)" }}>
            <CheckCircle size={20} color="var(--success-500)" /> {result.medicine.particulars}
          </h3>
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
            <div className="last-purchase-card" style={{ marginTop: "16px", background: "var(--bg-muted)", padding: "12px", borderRadius: "8px" }}>
              <div className="title" style={{ display: "flex", alignItems: "center", gap: "6px", fontWeight: 600, color: "var(--text-main)", marginBottom: "8px" }}>
                <Package size={16} /> Last arrived
              </div>
              <div style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "4px" }}>
                {result.stock.last_purchase.qty_received} units from <strong style={{ color: "var(--text-main)" }}>{result.stock.last_purchase.distributor_name || "unknown"}</strong>
              </div>
              <div style={{ fontSize: "13px", color: "var(--text-secondary)" }}>Rate: ₹{result.stock.last_purchase.rate ?? "—"}</div>
            </div>
          )}
        </motion.div>
      )}

      {result && !result.found && (
        <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="card" style={{ borderLeft: "4px solid var(--warning-500)" }}>
          <h3 style={{ marginTop: 0, display: "flex", alignItems: "center", gap: "8px", color: "var(--text-main)" }}>
            <SearchIcon size={20} color="var(--warning-500)" /> Barcode not recognized yet
          </h3>
          <p style={{ color: "var(--text-secondary)", fontSize: "13px", lineHeight: 1.5 }}>
            This code (<code style={{ background: "var(--bg-muted)", padding: "2px 4px", borderRadius: "4px" }}>{lastCode}</code>) isn't linked to any medicine yet. Search and select the
            correct one below to link it — future scans will resolve instantly.
          </p>
          <div style={{ position: "relative", marginTop: "16px" }}>
            <SearchIcon size={16} style={{ position: "absolute", left: "12px", top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }} />
            <input
              style={{ width: "100%", paddingLeft: "36px" }}
              placeholder="Search medicine name..."
              value={linkQuery}
              onChange={(e) => setLinkQuery(e.target.value)}
            />
          </div>
          {linkResults.length > 0 && (
            <div style={{ marginTop: "12px", border: "1px solid var(--border-color)", borderRadius: "8px", overflow: "hidden" }}>
              <table className="table" style={{ margin: 0, width: "100%" }}>
                <tbody>
                  {linkResults.map((m) => (
                    <tr key={m.id} style={{ transition: "background 0.2s ease" }} className="hover-row">
                      <td style={{ padding: "12px", borderBottom: "1px solid var(--border-color)" }}>
                        <div style={{ fontWeight: 600, color: "var(--text-main)" }}>{m.particulars}</div>
                        <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>{m.unit}</div>
                      </td>
                      <td style={{ padding: "12px", textAlign: "right", borderBottom: "1px solid var(--border-color)" }}>
                        <button className="btn secondary" onClick={() => handleLinkMedicine(m.id)} disabled={linking}>
                          {linking ? "Linking..." : "Link this"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </motion.div>
      )}
      <style>{`
        .spin { animation: spin 1s linear infinite; }
        @keyframes spin { 100% { transform: rotate(360deg); } }
        .hover-row:hover { background: var(--bg-muted); }
      `}</style>
    </motion.div>
  );
}