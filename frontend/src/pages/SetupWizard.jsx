import { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  Upload, FileSpreadsheet, CheckCircle, AlertCircle,
  Loader, ArrowRight, Info, Hexagon, ChevronRight
} from "lucide-react";
import { api, getToken } from "../api/client.js";
import { useAuth } from "../auth/AuthContext.jsx";

const STEPS = [
  { id: 1, label: "Upload List" },
  { id: 2, label: "Processing" },
  { id: 3, label: "Done!" },
];

function ProgressBar({ pct }) {
  return (
    <div style={{ height: 8, background: "var(--bg-subtle, #e2e8f0)", borderRadius: 99, overflow: "hidden" }}>
      <motion.div
        animate={{ width: `${pct}%` }}
        transition={{ duration: 0.5, ease: "easeOut" }}
        style={{
          height: "100%",
          background: "linear-gradient(90deg, var(--primary-500), var(--primary-700))",
          borderRadius: 99,
        }}
      />
    </div>
  );
}

export default function SetupWizard() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [step, setStep] = useState(1);
  const [file, setFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [importing, setImporting] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState(null);  // { imported, skipped, errors }
  const [error, setError] = useState(null);
  const fileInputRef = useRef(null);

  function handleDrop(e) {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped && (dropped.name.endsWith(".xlsx") || dropped.name.endsWith(".xls") || dropped.name.endsWith(".csv"))) {
      setFile(dropped);
    } else {
      setError("Please upload an Excel (.xlsx, .xls) or CSV file.");
    }
  }

  function handleFileSelect(e) {
    const selected = e.target.files[0];
    if (selected) setFile(selected);
  }

  async function handleUpload() {
    if (!file) return;
    setImporting(true);
    setError(null);
    setStep(2);
    setProgress(10);

    try {
      // Simulate progress while uploading
      const progressInterval = setInterval(() => {
        setProgress((p) => Math.min(p + 5, 85));
      }, 300);

      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch("/api/setup/import-medicine-list", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${getToken()}`,
        },
        body: formData,
      });

      clearInterval(progressInterval);
      setProgress(100);

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Import failed");

      setResult(data);
      setStep(3);
    } catch (err) {
      setError(err.message);
      setStep(1);
      setProgress(0);
    } finally {
      setImporting(false);
    }
  }

  return (
    <div style={{
      minHeight: "100vh", background: "var(--bg-app)",
      display: "flex", flexDirection: "column",
    }}>
      {/* Header */}
      <div style={{
        padding: "16px 32px",
        background: "rgba(255,255,255,0.8)", backdropFilter: "blur(20px)",
        borderBottom: "1px solid var(--border-subtle)",
        display: "flex", alignItems: "center", gap: 12,
      }}>
        <div style={{
          background: "linear-gradient(135deg, var(--primary-500), var(--primary-700))",
          color: "#fff", width: 36, height: 36, borderRadius: 10,
          display: "flex", alignItems: "center", justifyContent: "center"
        }}>
          <Hexagon size={20} strokeWidth={2.5} />
        </div>
        <span style={{ fontWeight: 800, fontSize: "1.1rem", color: "var(--primary-600)" }}>PharmOS</span>
        <span style={{ color: "var(--text-muted)", fontSize: "var(--text-sm)" }}>
          → Setup Wizard
        </span>
      </div>

      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: "40px 24px" }}>
        <div style={{ width: "100%", maxWidth: 580 }}>

          {/* Welcome message */}
          {user && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              style={{
                background: "linear-gradient(135deg, var(--primary-50), var(--primary-100))",
                border: "1px solid var(--primary-200)",
                borderRadius: "var(--radius-xl)",
                padding: "var(--space-4) var(--space-5)",
                marginBottom: "var(--space-6)",
                display: "flex", alignItems: "center", gap: 12,
              }}
            >
              <div style={{
                width: 40, height: 40, background: "var(--primary-600)", borderRadius: "50%",
                display: "flex", alignItems: "center", justifyContent: "center",
                color: "#fff", fontWeight: 800, fontSize: 16, flexShrink: 0,
              }}>
                {(user.full_name || user.username || "?").charAt(0).toUpperCase()}
              </div>
              <div>
                <div style={{ fontWeight: 700, color: "var(--text-main)", fontSize: "var(--text-sm)" }}>
                  Welcome, {user.full_name || user.username}! 👋
                </div>
                <div style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)" }}>
                  Your PharmOS account is ready. Let's import your medicine list.
                </div>
              </div>
            </motion.div>
          )}

          {/* Step indicator */}
          <div style={{ display: "flex", alignItems: "center", marginBottom: "var(--space-8)", gap: 0 }}>
            {STEPS.map((s, i) => (
              <div key={s.id} style={{ display: "flex", alignItems: "center", flex: i < STEPS.length - 1 ? 1 : 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <div style={{
                    width: 28, height: 28, borderRadius: "50%",
                    background: step >= s.id ? "var(--primary-600)" : "var(--bg-subtle, #e2e8f0)",
                    color: step >= s.id ? "#fff" : "var(--text-muted)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontWeight: 700, fontSize: 12, flexShrink: 0,
                    transition: "all 0.3s",
                  }}>
                    {step > s.id ? <CheckCircle size={14} /> : s.id}
                  </div>
                  <span style={{
                    fontSize: "var(--text-xs)", fontWeight: 600,
                    color: step >= s.id ? "var(--primary-600)" : "var(--text-muted)",
                    whiteSpace: "nowrap",
                  }}>
                    {s.label}
                  </span>
                </div>
                {i < STEPS.length - 1 && (
                  <div style={{
                    flex: 1, height: 2, margin: "0 12px",
                    background: step > s.id ? "var(--primary-400)" : "var(--border-subtle)",
                    transition: "background 0.3s",
                  }} />
                )}
              </div>
            ))}
          </div>

          <AnimatePresence mode="wait">
            {/* ── STEP 1: Upload ───────────────────────────────────────── */}
            {step === 1 && (
              <motion.div
                key="upload"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.3 }}
              >
                <div className="card" style={{ padding: "var(--space-8)" }}>
                  <h2 style={{ margin: "0 0 8px", fontSize: "var(--text-2xl)", fontWeight: 800, color: "var(--text-main)", fontFamily: "var(--font-display)" }}>
                    Upload Your Medicine Rate List
                  </h2>
                  <p style={{ margin: "0 0 var(--space-6)", color: "var(--text-muted)", fontSize: "var(--text-sm)", lineHeight: 1.6 }}>
                    Upload your existing Excel sheet. We'll import all your medicines — names, MRP, net rate, company, and more.
                  </p>

                  {/* Info box */}
                  <div style={{
                    background: "var(--primary-50)", border: "1px solid var(--primary-200)",
                    borderRadius: "var(--radius-lg)", padding: "var(--space-4)",
                    marginBottom: "var(--space-5)",
                    display: "flex", gap: 10,
                  }}>
                    <Info size={16} style={{ color: "var(--primary-600)", flexShrink: 0, marginTop: 1 }} />
                    <div style={{ fontSize: "var(--text-xs)", color: "var(--primary-800)", lineHeight: 1.6 }}>
                      <strong>Expected columns:</strong> Particulars, Unit, MRP, Net Rate, Company (same format as your current Excel).
                      Extra columns are ignored. Column names are matched case-insensitively.
                    </div>
                  </div>

                  {/* Drop zone */}
                  <div
                    onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                    onDragLeave={() => setDragOver(false)}
                    onDrop={handleDrop}
                    onClick={() => fileInputRef.current?.click()}
                    style={{
                      border: `2px dashed ${dragOver ? "var(--primary-500)" : file ? "var(--primary-400)" : "var(--border-strong)"}`,
                      borderRadius: "var(--radius-xl)",
                      padding: "var(--space-8)",
                      textAlign: "center",
                      cursor: "pointer",
                      background: dragOver ? "var(--primary-50)" : file ? "var(--primary-50)" : "transparent",
                      transition: "all 0.2s",
                    }}
                  >
                    <input
                      type="file"
                      accept=".xlsx,.xls,.csv"
                      ref={fileInputRef}
                      style={{ display: "none" }}
                      onChange={handleFileSelect}
                    />
                    {file ? (
                      <motion.div initial={{ scale: 0.9 }} animate={{ scale: 1 }}>
                        <FileSpreadsheet size={40} style={{ color: "var(--primary-600)", marginBottom: 12 }} />
                        <div style={{ fontWeight: 700, color: "var(--text-main)", marginBottom: 4 }}>{file.name}</div>
                        <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
                          {(file.size / 1024).toFixed(1)} KB · Click to change
                        </div>
                      </motion.div>
                    ) : (
                      <>
                        <Upload size={36} style={{ color: "var(--text-muted)", marginBottom: 12 }} />
                        <div style={{ fontWeight: 600, color: "var(--text-main)", marginBottom: 4 }}>
                          Drag & drop your Excel file here
                        </div>
                        <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
                          or click to browse · Supports .xlsx, .xls, .csv
                        </div>
                      </>
                    )}
                  </div>

                  {error && (
                    <motion.div
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      style={{
                        marginTop: "var(--space-4)",
                        background: "var(--danger-bg)", color: "var(--danger-text)",
                        padding: "var(--space-3)", borderRadius: "var(--radius-md)",
                        fontSize: "var(--text-sm)", display: "flex", alignItems: "center", gap: 8,
                        border: "1px solid var(--danger-border)",
                      }}
                    >
                      <AlertCircle size={16} />
                      {error}
                    </motion.div>
                  )}

                  <div style={{ marginTop: "var(--space-6)", display: "flex", gap: 12 }}>
                    <motion.button
                      className="btn btn-primary"
                      style={{ flex: 1, padding: "var(--space-3)", fontSize: "var(--text-base)", fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      onClick={handleUpload}
                      disabled={!file}
                    >
                      Import Medicine List
                      <ArrowRight size={18} />
                    </motion.button>
                    <motion.button
                      style={{ padding: "var(--space-3) var(--space-5)", fontSize: "var(--text-sm)", fontWeight: 600, background: "none", border: "1px solid var(--border-strong)", borderRadius: "var(--radius-lg)", cursor: "pointer", color: "var(--text-main)" }}
                      whileHover={{ scale: 1.02 }}
                      onClick={() => navigate("/")}
                    >
                      Skip
                    </motion.button>
                  </div>
                </div>
              </motion.div>
            )}

            {/* ── STEP 2: Processing ───────────────────────────────────── */}
            {step === 2 && (
              <motion.div
                key="processing"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3 }}
              >
                <div className="card" style={{ padding: "var(--space-8)", textAlign: "center" }}>
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                    style={{ display: "inline-block", marginBottom: 24 }}
                  >
                    <Loader size={48} style={{ color: "var(--primary-600)" }} />
                  </motion.div>
                  <h2 style={{ margin: "0 0 8px", fontSize: "var(--text-xl)", fontWeight: 800, color: "var(--text-main)" }}>
                    Importing Your Medicine List…
                  </h2>
                  <p style={{ color: "var(--text-muted)", margin: "0 0 32px", fontSize: "var(--text-sm)" }}>
                    Reading {file?.name} and creating your medicine catalog
                  </p>
                  <ProgressBar pct={progress} />
                  <p style={{ marginTop: 8, color: "var(--text-muted)", fontSize: "var(--text-xs)" }}>
                    {progress < 50 ? "Reading file…" : progress < 85 ? "Processing medicines…" : "Finalizing…"}
                  </p>
                </div>
              </motion.div>
            )}

            {/* ── STEP 3: Done ─────────────────────────────────────────── */}
            {step === 3 && result && (
              <motion.div
                key="done"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.4, type: "spring" }}
              >
                <div className="card" style={{ padding: "var(--space-8)", textAlign: "center" }}>
                  <motion.div
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ type: "spring", stiffness: 200, delay: 0.1 }}
                    style={{
                      width: 72, height: 72, margin: "0 auto 20px",
                      background: "linear-gradient(135deg, #10b981, #059669)",
                      borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center",
                      color: "#fff", boxShadow: "0 10px 20px rgba(16, 185, 129, 0.3)",
                    }}
                  >
                    <CheckCircle size={36} />
                  </motion.div>

                  <h2 style={{ margin: "0 0 8px", fontSize: "var(--text-2xl)", fontWeight: 800, color: "var(--text-main)" }}>
                    Import Complete! 🎉
                  </h2>
                  <p style={{ color: "var(--text-muted)", margin: "0 0 32px", lineHeight: 1.6 }}>
                    Your medicine catalog is ready. All features are now active.
                  </p>

                  {/* Stats */}
                  <div style={{
                    display: "grid", gridTemplateColumns: "1fr 1fr 1fr",
                    gap: 16, marginBottom: 32,
                  }}>
                    {[
                      { label: "Imported", value: result.imported ?? 0, color: "#10b981" },
                      { label: "Skipped", value: result.skipped ?? 0, color: "#f59e0b" },
                      { label: "Errors", value: result.errors ?? 0, color: "#ef4444" },
                    ].map((s) => (
                      <div key={s.label} style={{
                        background: "var(--bg-subtle, #f8fafc)", borderRadius: "var(--radius-lg)",
                        padding: "var(--space-4)", border: "1px solid var(--border-subtle)",
                      }}>
                        <div style={{ fontSize: "1.6rem", fontWeight: 800, color: s.color }}>{s.value}</div>
                        <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>{s.label}</div>
                      </div>
                    ))}
                  </div>

                  <motion.button
                    className="btn btn-primary"
                    style={{ width: "100%", padding: "var(--space-3)", fontSize: "var(--text-base)", fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => navigate("/")}
                  >
                    Go to Dashboard
                    <ChevronRight size={18} />
                  </motion.button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Skip link below card */}
          {step === 1 && (
            <p style={{ textAlign: "center", marginTop: "var(--space-5)", fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>
              You can always import your medicine list later from{" "}
              <strong>Stock → Import</strong>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
