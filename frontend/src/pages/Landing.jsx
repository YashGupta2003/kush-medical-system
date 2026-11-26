import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Link } from "react-router-dom";
import { useLandingTheme } from "../utils/theme.js";
import {
  Hexagon,
  Scan,
  Bot,
  ShieldAlert,
  ShieldCheck,
  TrendingUp,
  Snowflake,
  Network,
  ArrowRight,
  CheckCircle2,
  Database,
  Lock,
  FileText,
  AlertTriangle,
  Link2,
  Code2,
  Layers,
  Cpu,
  Sun,
  Moon,
  Sparkles,
} from "lucide-react";
import "../styles/landing.css";

const WORKBENCH_TABS = [
  { id: "pos", label: "POS Safety Guardrail", icon: ShieldAlert },
  { id: "ocr", label: "Bill OCR Engine", icon: Scan },
  { id: "copilot", label: "PharmaCopilot AI", icon: Bot },
  { id: "trustchain", label: "TrustChain Ledger", icon: Link2 },
];

const POS_SCENARIOS = {
  overlap: {
    pill: "Dolo 650 + Combiflam",
    invoice: "INV-2026-0412",
    total: "₹113.00",
    items: [
      { name: "DOLO 650 TABLETS", salt: "Paracetamol 650 mg", qty: "2 strips", mrp: "₹67.00", stock: "120 in stock" },
      { name: "COMBIFLAM TABLETS", salt: "Ibuprofen 400 mg + Paracetamol 325 mg", qty: "1 strip", mrp: "₹46.00", stock: "150 in stock" },
    ],
    severity: "amber",
    badge: "MODERATE SALT OVERLAP",
    alertTitle: "Duplicate Active Ingredient Guardrail Triggered",
    alertBody:
      "Concurrent Paracetamol found in both DOLO 650 and COMBIFLAM (975 mg combined dose). Pharmacist confirmation required before dispensing.",
    statusText: "Override Needed",
  },
  ddi: {
    pill: "Aspirin + Warfarin",
    invoice: "INV-2026-0413",
    total: "₹148.50",
    items: [
      { name: "ECOSPRIN 75 TABLETS", salt: "Aspirin 75 mg", qty: "1 strip", mrp: "₹24.50", stock: "84 in stock" },
      { name: "WARF 5 TABLETS", salt: "Warfarin 5 mg", qty: "1 strip", mrp: "₹124.00", stock: "32 in stock" },
    ],
    severity: "rose",
    badge: "MAJOR DRUG INTERACTION",
    alertTitle: "High-Severity Bleeding Risk Detected",
    alertBody:
      "PharmaGraph detected a Major interaction edge: Aspirin + Warfarin markedly increases hemorrhage risk. Verify prescriber authorization first.",
    statusText: "Blocked Until Override",
  },
  safe: {
    pill: "PAN-D + Shelcal 500",
    invoice: "INV-2026-0414",
    total: "₹338.50",
    items: [
      { name: "PAN-D CAPSULES", salt: "Pantoprazole 40 mg + Domperidone 30 mg", qty: "1 strip", mrp: "₹199.00", stock: "80 in stock" },
      { name: "SHELCAL 500 TABLETS", salt: "Calcium 500 mg + Vitamin D3 250 IU", qty: "1 strip", mrp: "₹139.50", stock: "85 in stock" },
    ],
    severity: "emerald",
    badge: "ALL CLEAR · SAFE",
    alertTitle: "No Clinical Conflicts Found",
    alertBody:
      "Zero duplicate salts and zero interaction edges across all active ingredients. Atomic POS stock decrement & GST snapshot ready.",
    statusText: "Ready to Dispense",
  },
};

const OCR_ROWS = [
  {
    name: "AUGMENTIN 625 DUO TAB",
    qty: "10 + 1",
    mrp: "223.50",
    rate: "168.00",
    disc: "5% + 2%",
    gst: "12%",
    landed: "₹160.27",
    formula: "(168 × 10 × 0.95 × 0.98 × 1.12) / 11 = ₹160.27 / unit",
  },
  {
    name: "PAN-D CAPSULES (15S)",
    qty: "20 + 2",
    mrp: "199.00",
    rate: "148.50",
    disc: "5% + 0%",
    gst: "12%",
    landed: "₹143.64",
    formula: "(148.50 × 20 × 0.95 × 1.12) / 22 = ₹143.64 / unit",
  },
  {
    name: "AZITHRAL 500 MG",
    qty: "15 + 0",
    mrp: "132.00",
    rate: "94.28",
    disc: "0% + 0%",
    gst: "12%",
    landed: "₹105.59",
    formula: "(94.28 × 15 × 1.12) / 15 = ₹105.59 / unit",
  },
];

const COPILOT_PROMPTS = {
  expiry: {
    pill: "Low stock & expiring in 30d",
    question: "Which medicines are below threshold or expiring in the next 30 days?",
    tools: ["get_analytics_overview()", "get_expiring_medicines(days=30)", "get_low_stock_items()"],
    answer:
      "Shelf valuation is ₹56,812.00 (net cost). MONTEK-LC TABLETS is at 10 strips (below reorder point 15). One batch of COMBIFLAM expires in 19 days — recommended for Inter-Pharmacy Network listing.",
  },
  margins: {
    pill: "Higher-margin salt substitutes",
    question: "Find higher-margin substitutes for AUGMENTIN 625 DUO in our catalog.",
    tools: ["search_medicines('AUGMENTIN')", "get_best_margin_substitutes(med_id=2)"],
    answer:
      "AUGMENTIN 625 DUO runs a 20.0% retail margin (MRP ₹223.50 / Cost ₹178.80). Matching Amoxicillin 500 + Clavulanic Acid 125 alternative in stock offers 28.4% margin with 45 units available.",
  },
  gst: {
    pill: "Monthly GST summary check",
    question: "Summarize confirmed bill spend and CGST/SGST input tax credit this month.",
    tools: ["get_gst_report(year=2026, month=11)", "get_distributor_breakdown()"],
    answer:
      "Confirmed purchase taxable total is ₹84,200.00 across 6 bills: ₹5,052.00 CGST + ₹5,052.00 SGST input credit (12% & 5% slabs verified by supplier GSTIN state codes).",
  },
};

const TECH_STACK = [
  { name: "FastAPI + Pydantic v2", role: "Versioned REST (/v1)" },
  { name: "React 18 + Vite", role: "Interactive SPA" },
  { name: "SQLAlchemy Hooks", role: "Tenant Isolation" },
  { name: "Vision + Tesseract", role: "Hybrid Invoice OCR" },
  { name: "Groq Llama 3.3 70B", role: "Tool-Calling Copilot" },
  { name: "Statsmodels + Scikit-Learn", role: "Forecast & Anomalies" },
  { name: "ReportLab + Alembic", role: "GST PDF & 31 Revisions" },
];

const ARCHITECTURE_PILLARS = [
  {
    icon: Lock,
    tag: "MULTI-TENANCY",
    title: "Session-Level Tenant Isolation",
    desc: "Every ORM query and flush passes through do_orm_execute and before_flush hooks, isolating inventory, bills, sales, and customer ledgers per shop.",
    metric: "Zero Cross-Shop Leaks",
    tone: "emerald",
  },
  {
    icon: Database,
    tag: "CONCURRENCY",
    title: "Atomic Stock & Invoice Locks",
    desc: "POS decrements enforce row locks and DB-level non-negative CHECK constraints, paired with confirmed_invoice_key uniqueness & Redis idempotency.",
    metric: "ACID + Idempotent POS",
    tone: "sky",
  },
  {
    icon: Link2,
    tag: "AUDITABILITY",
    title: "SHA-256 TrustChain Ledger",
    desc: "Rate edits, batch receipts, stock adjustments, and cold-chain excursions append to an immutable cryptographic hash chain verifiable anytime.",
    metric: "Tamper-Evident History",
    tone: "violet",
  },
  {
    icon: ShieldCheck,
    tag: "PRIVACY",
    title: "K-Anonymity Pulse (k ≥ 3)",
    desc: "Regional outbreak heatmaps aggregate opted-in OTC condition signals only when at least 3 distinct pharmacies contribute over a 7-day window.",
    metric: "Privacy-By-Construction",
    tone: "amber",
  },
];

const STEPS = [
  {
    num: "01",
    title: "Register Shop Tenant",
    desc: "Spin up an isolated pharmacy workspace with shop metadata, GSTIN state detection, and owner/staff RBAC.",
    pill: "JWT + HttpOnly Refresh",
  },
  {
    num: "02",
    title: "Import Catalog or Scan Bills",
    desc: "Upload your existing Excel/CSV rate list in seconds or snap distributor invoices to populate batches and landed costs.",
    pill: "Tesseract / Cloud Vision",
  },
  {
    num: "03",
    title: "Dispense Safely & Track Profit",
    desc: "Bill customers with live salt-interaction guards, export CA-ready GST PDFs, and query PharmaCopilot anytime.",
    pill: "7 Active AI Pillars",
  },
];

function HeroWorkbench() {
  const [activeTab, setActiveTab] = useState("pos");
  const [posKey, setPosKey] = useState("overlap");
  const [ocrIndex, setOcrIndex] = useState(0);
  const [copilotKey, setCopilotKey] = useState("expiry");
  const [chainVerified, setChainVerified] = useState(true);

  const posData = POS_SCENARIOS[posKey];
  const selectedOcr = OCR_ROWS[ocrIndex];
  const copilotData = COPILOT_PROMPTS[copilotKey];

  const toneVars = (tone) => ({
    text: `var(--l-${tone}-text)`,
    bg: `var(--l-${tone}-soft)`,
    border: `var(--l-${tone}-border)`,
  });

  const posTone = toneVars(posData.severity);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.55, delay: 0.15 }}
      className="workbench-shell"
    >
      {/* Top Window Chrome & Interactive Tab Switcher */}
      <div className="workbench-topbar">
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ display: "flex", gap: 6 }}>
            <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#ef4444" }} />
            <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#f59e0b" }} />
            <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#10b981" }} />
          </div>
          <span className="mono-tag" style={{ color: "var(--l-text-muted)", fontSize: "0.7rem" }}>
            interactive-demo · tenant/kush-medical
          </span>
        </div>

        <div className="workbench-tabs" role="tablist" aria-label="Interactive workspace preview">
          {WORKBENCH_TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={isActive}
                onClick={() => setActiveTab(tab.id)}
                className={`workbench-tab ${isActive ? "active" : ""}`}
              >
                <Icon size={14} />
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Interactive Preview Stage */}
      <div className="workbench-body">
        <AnimatePresence mode="wait">
          {activeTab === "pos" && (
            <motion.div
              key="pos"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.18 }}
              style={{ textAlign: "left", display: "flex", flexDirection: "column", gap: 14 }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
                <span className="mono-tag" style={{ color: "var(--l-text-muted)" }}>Test Clinical Scenarios Live:</span>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {Object.entries(POS_SCENARIOS).map(([key, sc]) => (
                    <button
                      key={key}
                      type="button"
                      onClick={() => setPosKey(key)}
                      className={`sim-chip ${posKey === key ? "active" : ""}`}
                    >
                      {sc.pill}
                    </button>
                  ))}
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))", gap: 14 }}>
                {/* Cart */}
                <div style={{ background: "var(--l-surface-inset)", border: "1px solid var(--l-border)", borderRadius: 14, padding: 15 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                    <span style={{ fontSize: "0.84rem", fontWeight: 700, color: "var(--l-text-primary)" }}>Counter Basket</span>
                    <span className="mono-tag" style={{ padding: "3px 8px", borderRadius: 6, background: "var(--l-emerald-soft)", color: "var(--l-emerald-text)" }}>
                      {posData.invoice}
                    </span>
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {posData.items.map((item) => (
                      <div
                        key={item.name}
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          padding: "10px 12px",
                          borderRadius: 10,
                          background: "var(--l-card-bg)",
                          border: "1px solid var(--l-border)",
                        }}
                      >
                        <div>
                          <div style={{ fontSize: "0.84rem", fontWeight: 700, color: "var(--l-text-primary)" }}>{item.name}</div>
                          <div style={{ fontSize: "0.73rem", color: "var(--l-text-muted)", marginTop: 2 }}>{item.salt} · {item.stock}</div>
                        </div>
                        <div style={{ textAlign: "right" }}>
                          <div style={{ fontSize: "0.84rem", fontWeight: 700, color: "var(--l-text-primary)", fontFamily: "var(--font-mono)" }}>{item.mrp}</div>
                          <div style={{ fontSize: "0.7rem", color: "var(--l-text-muted)" }}>{item.qty}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginTop: 12, paddingTop: 10, borderTop: "1px solid var(--l-border)", fontSize: "0.82rem" }}>
                    <span style={{ color: "var(--l-text-muted)" }}>Net Total (GST Included)</span>
                    <strong style={{ color: "var(--l-emerald-text)", fontFamily: "var(--font-mono)" }}>{posData.total}</strong>
                  </div>
                </div>

                {/* Live Guardrail */}
                <div style={{ display: "flex", flexDirection: "column", justifyContent: "space-between", gap: 12 }}>
                  <div style={{ background: posTone.bg, border: `1px solid ${posTone.border}`, borderRadius: 14, padding: 15 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, marginBottom: 8 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 7, color: posTone.text, fontWeight: 700, fontSize: "0.86rem" }}>
                        {posData.severity === "emerald" ? <CheckCircle2 size={17} /> : <AlertTriangle size={17} />}
                        {posData.alertTitle}
                      </div>
                    </div>
                    <p style={{ fontSize: "0.8rem", color: "var(--l-text-secondary)", lineHeight: 1.55, margin: "0 0 12px" }}>
                      {posData.alertBody}
                    </p>
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                      <span className="mono-tag" style={{ padding: "4px 9px", borderRadius: 6, background: "var(--l-card-bg)", border: `1px solid ${posTone.border}`, color: posTone.text }}>
                        {posData.badge}
                      </span>
                      <span className="mono-tag" style={{ padding: "4px 9px", borderRadius: 6, background: "var(--l-card-bg)", border: "1px solid var(--l-border)", color: "var(--l-text-secondary)" }}>
                        {posData.statusText}
                      </span>
                    </div>
                  </div>

                  <div style={{ background: "var(--l-surface-inset)", border: "1px solid var(--l-border)", borderRadius: 12, padding: "12px 14px", display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.8rem" }}>
                    <div>
                      <div className="mono-tag" style={{ color: "var(--l-text-muted)", fontSize: "0.66rem" }}>CUSTOMER CREDIT / ADHERENCE</div>
                      <div style={{ fontWeight: 700, color: "var(--l-text-primary)", marginTop: 2 }}>Rahul Sharma · +91 98111 22233</div>
                    </div>
                    <span className="mono-tag" style={{ color: "var(--l-sky-text)", fontWeight: 700 }}>Udhaar Ready</span>
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {activeTab === "ocr" && (
            <motion.div
              key="ocr"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.18 }}
              style={{ textAlign: "left", display: "flex", flexDirection: "column", gap: 14 }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10 }}>
                <div>
                  <div style={{ fontSize: "0.94rem", fontWeight: 700, color: "var(--l-text-primary)" }}>
                    Hari Krishna Distributor — Invoice #HK-8842
                  </div>
                  <div style={{ fontSize: "0.78rem", color: "var(--l-text-muted)" }}>
                    Click any row below to inspect its exact landed cost formula
                  </div>
                </div>
                <span className="mono-tag" style={{ padding: "5px 10px", borderRadius: 9999, background: "var(--l-emerald-soft)", color: "var(--l-emerald-text)", border: "1px solid var(--l-emerald-border)" }}>
                  96.4% Layout Confidence
                </span>
              </div>

              <div style={{ overflowX: "auto", border: "1px solid var(--l-border)", borderRadius: 12, background: "var(--l-surface-inset)" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8rem" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--l-border)", color: "var(--l-text-muted)", fontSize: "0.7rem", textTransform: "uppercase" }}>
                      <th style={{ padding: "10px 12px", textAlign: "left" }}>Extracted Item</th>
                      <th style={{ padding: "10px 8px", textAlign: "right" }}>Qty + Free</th>
                      <th style={{ padding: "10px 8px", textAlign: "right" }}>Rate</th>
                      <th style={{ padding: "10px 8px", textAlign: "right" }}>Disc</th>
                      <th style={{ padding: "10px 8px", textAlign: "right" }}>GST</th>
                      <th style={{ padding: "10px 12px", textAlign: "right" }}>Landed Cost</th>
                    </tr>
                  </thead>
                  <tbody style={{ fontFamily: "var(--font-mono)" }}>
                    {OCR_ROWS.map((r, i) => {
                      const active = ocrIndex === i;
                      return (
                        <tr
                          key={r.name}
                          onClick={() => setOcrIndex(i)}
                          style={{
                            cursor: "pointer",
                            borderBottom: "1px solid var(--l-border)",
                            background: active ? "var(--l-emerald-soft)" : "transparent",
                            color: "var(--l-text-primary)",
                            transition: "background 140ms ease",
                          }}
                        >
                          <td style={{ padding: "10px 12px", fontFamily: "var(--font-body)", fontWeight: 600 }}>{r.name}</td>
                          <td style={{ padding: "10px 8px", textAlign: "right", color: "var(--l-text-muted)" }}>{r.qty}</td>
                          <td style={{ padding: "10px 8px", textAlign: "right" }}>₹{r.rate}</td>
                          <td style={{ padding: "10px 8px", textAlign: "right", color: "var(--l-amber-text)" }}>{r.disc}</td>
                          <td style={{ padding: "10px 8px", textAlign: "right", color: "var(--l-sky-text)" }}>{r.gst}</td>
                          <td style={{ padding: "10px 12px", textAlign: "right", color: "var(--l-emerald-text)", fontWeight: 700 }}>{r.landed}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div style={{ padding: "11px 14px", borderRadius: 10, background: "var(--l-surface-inset)", border: "1px solid var(--l-border-strong)", fontFamily: "var(--font-mono)", fontSize: "0.75rem", color: "var(--l-text-secondary)", display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
                <span><strong>{selectedOcr.name}:</strong> {selectedOcr.formula}</span>
                <span style={{ color: "var(--l-emerald-text)", fontWeight: 700 }}>Stock + Batch + TrustChain Ready</span>
              </div>
            </motion.div>
          )}

          {activeTab === "copilot" && (
            <motion.div
              key="copilot"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.18 }}
              style={{ textAlign: "left", display: "flex", flexDirection: "column", gap: 12 }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
                <span className="mono-tag" style={{ color: "var(--l-text-muted)" }}>Try Copilot Queries:</span>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {Object.entries(COPILOT_PROMPTS).map(([k, p]) => (
                    <button
                      key={k}
                      type="button"
                      onClick={() => setCopilotKey(k)}
                      className={`sim-chip ${copilotKey === k ? "active" : ""}`}
                    >
                      {p.pill}
                    </button>
                  ))}
                </div>
              </div>

              <div style={{ alignSelf: "flex-end", maxWidth: "88%", padding: "10px 14px", borderRadius: "14px 14px 4px 14px", background: "var(--l-emerald-soft)", border: "1px solid var(--l-emerald-border)", color: "var(--l-text-primary)", fontSize: "0.84rem", fontWeight: 600 }}>
                "{copilotData.question}"
              </div>

              <div style={{ background: "var(--l-surface-inset)", border: "1px solid var(--l-border)", borderRadius: 12, padding: "10px 12px" }}>
                <div className="mono-tag" style={{ color: "var(--l-sky-text)", marginBottom: 6 }}>
                  GROQ ALLOWLIST TOOL TRACE · NO RAW SQL GENERATED
                </div>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", fontFamily: "var(--font-mono)", fontSize: "0.73rem" }}>
                  {copilotData.tools.map((t) => (
                    <span key={t} style={{ padding: "4px 8px", borderRadius: 6, background: "var(--l-sky-soft)", color: "var(--l-sky-text)", border: "1px solid var(--l-sky-border)" }}>
                      ✓ {t}
                    </span>
                  ))}
                </div>
              </div>

              <div style={{ background: "var(--l-surface-inset)", border: "1px solid var(--l-border)", borderRadius: 12, padding: 14, fontSize: "0.84rem", lineHeight: 1.6, color: "var(--l-text-secondary)" }}>
                <strong style={{ color: "var(--l-emerald-text)" }}>Grounded Shop Reply:</strong> {copilotData.answer}
              </div>
            </motion.div>
          )}

          {activeTab === "trustchain" && (
            <motion.div
              key="trustchain"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.18 }}
              style={{ textAlign: "left", display: "flex", flexDirection: "column", gap: 12 }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10 }}>
                <div>
                  <div style={{ fontSize: "0.94rem", fontWeight: 700, color: "var(--l-text-primary)" }}>TrustChain Immutable Audit Ledger</div>
                  <div style={{ fontSize: "0.76rem", color: "var(--l-text-muted)" }}>Click verify to run cryptographic SHA-256 continuity verification</div>
                </div>
                <button
                  type="button"
                  onClick={() => setChainVerified((v) => !v)}
                  className="sim-chip active"
                  style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
                >
                  <CheckCircle2 size={13} />
                  {chainVerified ? "CHAIN INTACT · 3/3 VERIFIED ✓" : "RE-RUN SHA-256 VERIFICATION"}
                </button>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 8, fontFamily: "var(--font-mono)", fontSize: "0.75rem" }}>
                {[
                  { seq: "#1043", type: "cold_chain_reading", detail: "Vaccine Fridge A · Temp 4.2°C (Compliant)", prev: "8f31c2…b9a1", hash: "e740a9…31fd" },
                  { seq: "#1042", type: "rate_change", detail: "AUGMENTIN 625 · ₹161.20 → ₹168.00", prev: "4a9d02…771e", hash: "8f31c2…b9a1" },
                  { seq: "#1041", type: "bill_confirmed", detail: "Bill #HK-8842 · Hari Krishna Dist", prev: "10bc98…09aa", hash: "4a9d02…771e" },
                ].map((b) => (
                  <div
                    key={b.seq}
                    style={{
                      display: "grid",
                      gridTemplateColumns: "auto 1fr auto",
                      gap: 12,
                      alignItems: "center",
                      padding: "10px 12px",
                      borderRadius: 10,
                      background: "var(--l-surface-inset)",
                      border: `1px solid ${chainVerified ? "var(--l-emerald-border)" : "var(--l-border)"}`,
                    }}
                  >
                    <span style={{ color: "var(--l-emerald-text)", fontWeight: 700 }}>{b.seq}</span>
                    <div style={{ fontFamily: "var(--font-body)" }}>
                      <span className="mono-tag" style={{ color: "var(--l-violet-text)", marginRight: 8 }}>{b.type}</span>
                      <span style={{ color: "var(--l-text-primary)", fontSize: "0.8rem" }}>{b.detail}</span>
                    </div>
                    <span style={{ color: "var(--l-text-muted)" }}>
                      {b.prev} → <strong style={{ color: "var(--l-text-secondary)" }}>{b.hash}</strong>
                    </span>
                  </div>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}

export default function Landing() {
  const { theme, toggleTheme } = useLandingTheme();

  return (
    <div className="landing-root" data-landing-theme={theme}>
      <div className="landing-grid-bg" />
      <div className="landing-glow-left" />
      <div className="landing-glow-right" />

      {/* ── FULL-WIDTH STICKY GLASS NAVBAR ── */}
      <nav className="landing-nav">
        <Link to="/" style={{ display: "flex", alignItems: "center", gap: 10, textDecoration: "none", color: "var(--l-text-primary)" }}>
          <div style={{
            background: "var(--l-btn-primary-bg)",
            width: 36,
            height: 36,
            borderRadius: 10,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: "0 4px 14px rgba(16, 185, 129, 0.25)",
          }}>
            <Hexagon size={19} strokeWidth={2.5} color="#ffffff" />
          </div>
          <span style={{ fontFamily: "var(--font-display)", fontWeight: 800, fontSize: "1.18rem", letterSpacing: "-0.02em", color: "var(--l-text-primary)" }}>
            PharmOS
          </span>
          <span className="mono-tag" style={{ padding: "3px 8px", borderRadius: 9999, background: "var(--l-emerald-soft)", border: "1px solid var(--l-emerald-border)", color: "var(--l-emerald-text)", fontSize: "0.66rem" }}>
            v1.0
          </span>
        </Link>

        <div className="landing-nav-links">
          <a href="#modules" className="landing-nav-link">Modules</a>
          <a href="#architecture" className="landing-nav-link">Architecture</a>
          <a href="#workflow" className="landing-nav-link">Workflow</a>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <button
            type="button"
            onClick={toggleTheme}
            className="landing-theme-btn"
            aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          >
            {theme === "dark" ? <Sun size={15} color="#fbbf24" /> : <Moon size={15} color="#0284c7" />}
            <span>{theme === "dark" ? "Light" : "Dark"}</span>
          </button>
          <Link to="/login" className="landing-btn-secondary" style={{ padding: "8px 16px", fontSize: "0.85rem" }}>
            Sign In
          </Link>
          <Link to="/register" className="landing-btn-primary" style={{ padding: "8px 18px", fontSize: "0.85rem" }}>
            Register Shop
          </Link>
        </div>
      </nav>

      {/* ── FULL-PAGE SPLIT HERO SECTION ── */}
      <section style={{ padding: "48px 0 64px", position: "relative" }}>
        <div className="landing-container">
          <div className="hero-split-grid">
            {/* Left Column: Positioning, Value Prop, CTAs, Metrics */}
            <div>
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4 }}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 9,
                  padding: "6px 14px",
                  borderRadius: 9999,
                  background: "var(--l-emerald-soft)",
                  border: "1px solid var(--l-emerald-border)",
                  marginBottom: 22,
                }}
              >
                <span className="live-dot" />
                <span className="mono-tag" style={{ color: "var(--l-emerald-text)", fontWeight: 700 }}>
                  7 Intelligent Pillars · Multi-Tenant SaaS
                </span>
              </motion.div>

              <motion.h1
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: 0.06 }}
                style={{
                  fontFamily: "var(--font-display)",
                  fontSize: "clamp(2.2rem, 4.2vw, 3.85rem)",
                  fontWeight: 800,
                  lineHeight: 1.07,
                  letterSpacing: "-0.035em",
                  margin: "0 0 20px",
                }}
              >
                The Intelligent OS for{" "}
                <span style={{
                  background: "var(--l-headline-gradient)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                }}>
                  Modern Pharmacies.
                </span>
              </motion.h1>

              <motion.p
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: 0.12 }}
                style={{
                  fontSize: "clamp(0.98rem, 1.4vw, 1.12rem)",
                  color: "var(--l-text-secondary)",
                  lineHeight: 1.65,
                  margin: "0 0 28px",
                  maxWidth: 580,
                }}
              >
                Digitize supplier invoices with hybrid OCR, block dangerous drug interactions live at POS,
                forecast seasonal demand, and maintain a cryptographically verified GST audit trail.
              </motion.p>

              <motion.div
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: 0.18 }}
                style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 28 }}
              >
                <Link to="/register" className="landing-btn-primary">
                  Launch Your Pharmacy <ArrowRight size={17} />
                </Link>
                <Link to="/login" className="landing-btn-secondary">
                  Open Demo Workspace
                </Link>
              </motion.div>

              {/* Quick Interactive KPI Strip */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 10 }}>
                {[
                  { val: "474+", label: "Automated Tests", tone: "emerald" },
                  { val: "58 / 40", label: "Salts & DDI Rules", tone: "sky" },
                  { val: "k ≥ 3", label: "Privacy Pulse", tone: "violet" },
                ].map((stat) => (
                  <div
                    key={stat.label}
                    style={{
                      background: "var(--l-card-bg)",
                      border: "1px solid var(--l-border)",
                      borderRadius: 14,
                      padding: "12px 14px",
                      boxShadow: "var(--l-shadow-card)",
                    }}
                  >
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: "1.15rem", fontWeight: 700, color: `var(--l-${stat.tone}-text)` }}>
                      {stat.val}
                    </div>
                    <div style={{ fontSize: "0.75rem", color: "var(--l-text-muted)", fontWeight: 600, marginTop: 2 }}>
                      {stat.label}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Right Column: Full Interactive 4-Tab Workbench */}
            <HeroWorkbench />
          </div>
        </div>
      </section>

      {/* ── FULL-WIDTH TECH STACK STRIP ── */}
      <section style={{ borderTop: "1px solid var(--l-border)", borderBottom: "1px solid var(--l-border)", background: "var(--l-bg-band)", padding: "22px 0" }}>
        <div className="landing-container" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
          <span className="mono-tag" style={{ color: "var(--l-text-muted)", fontWeight: 700 }}>
            <Sparkles size={13} style={{ verticalAlign: "middle", marginRight: 6, color: "var(--l-emerald-text)" }} />
            Production Stack:
          </span>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {TECH_STACK.map((item) => (
              <div
                key={item.name}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "7px 12px",
                  borderRadius: 9999,
                  background: "var(--l-card-bg)",
                  border: "1px solid var(--l-border)",
                  fontSize: "0.78rem",
                }}
              >
                <span style={{ color: "var(--l-text-primary)", fontWeight: 700 }}>{item.name}</span>
                <span style={{ color: "var(--l-text-muted)" }}>· {item.role}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── FULL-PAGE MODULAR BENTO GRID (#modules) ── */}
      <section id="modules" style={{ padding: "76px 0" }}>
        <div className="landing-container">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexWrap: "wrap", gap: 20, marginBottom: 38 }}>
            <div style={{ maxWidth: 680 }}>
              <span className="mono-tag" style={{ color: "var(--l-emerald-text)", fontWeight: 700, display: "block", marginBottom: 10 }}>
                MODULAR ARCHITECTURE
              </span>
              <h2 style={{ fontFamily: "var(--font-display)", fontSize: "clamp(1.85rem, 3.4vw, 2.75rem)", fontWeight: 800, lineHeight: 1.12, letterSpacing: "-0.03em", margin: "0 0 10px" }}>
                Seven cohesive modules, engineered to sync automatically.
              </h2>
              <p style={{ color: "var(--l-text-secondary)", fontSize: "0.98rem", lineHeight: 1.6, margin: 0 }}>
                Confirming a single supplier invoice updates stock ledgers, expiry batches, margin trends, knowledge graphs, and TrustChain hashes in one atomic pipeline.
              </p>
            </div>
            <a href="#architecture" className="landing-btn-secondary" style={{ padding: "10px 18px", fontSize: "0.85rem" }}>
              Inspect System Design <ArrowRight size={15} />
            </a>
          </div>

          <div className="bento-grid">
            {/* Bento Card 1: OCR Pipeline (8 cols) */}
            <div className="bento-card bento-span-8">
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                  <div style={{ width: 42, height: 42, borderRadius: 12, background: "var(--l-emerald-soft)", border: "1px solid var(--l-emerald-border)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--l-emerald-text)" }}>
                    <Scan size={20} />
                  </div>
                  <span className="mono-tag" style={{ color: "var(--l-emerald-text)", background: "var(--l-emerald-soft)", border: "1px solid var(--l-emerald-border)", padding: "4px 10px", borderRadius: 9999 }}>
                    PILLAR 1 · BILL DIGITIZATION
                  </span>
                </div>
                <h3 style={{ fontFamily: "var(--font-display)", fontSize: "1.35rem", fontWeight: 700, margin: "0 0 8px" }}>
                  AI Invoice OCR + Distributor Layout Memory
                </h3>
                <p style={{ color: "var(--l-text-secondary)", fontSize: "0.92rem", lineHeight: 1.6, margin: "0 0 20px", maxWidth: 660 }}>
                  Photograph or batch-upload distributor bills. PharmOS deskews documents, parses table bounding boxes, remembers each supplier's column template from prior confirmations, and computes net landed cost per unit.
                </p>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 10 }}>
                {["1. Deskew & Clean", "2. Hybrid OCR", "3. Fuzzy Salt Match", "4. Cost & Batch Sync"].map((stage) => (
                  <div key={stage} style={{ padding: "10px 12px", borderRadius: 10, background: "var(--l-surface-inset)", border: "1px solid var(--l-border)", fontSize: "0.78rem", fontWeight: 600, color: "var(--l-text-primary)", fontFamily: "var(--font-mono)" }}>
                    {stage}
                  </div>
                ))}
              </div>
            </div>

            {/* Bento Card 2: PharmaCopilot (4 cols) */}
            <div className="bento-card bento-span-4">
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                  <div style={{ width: 42, height: 42, borderRadius: 12, background: "var(--l-violet-soft)", border: "1px solid var(--l-violet-border)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--l-violet-text)" }}>
                    <Bot size={20} />
                  </div>
                  <span className="mono-tag" style={{ color: "var(--l-violet-text)" }}>GROQ TOOL AGENT</span>
                </div>
                <h3 style={{ fontFamily: "var(--font-display)", fontSize: "1.3rem", fontWeight: 700, margin: "0 0 8px" }}>
                  PharmaCopilot
                </h3>
                <p style={{ color: "var(--l-text-secondary)", fontSize: "0.9rem", lineHeight: 1.6, margin: 0 }}>
                  Natural-language assistant that strictly invokes tested Python inventory, expiry, GST, and profit tools — zero arbitrary SQL or invented numbers.
                </p>
              </div>
              <div style={{ marginTop: 18, padding: "10px 12px", borderRadius: 10, background: "var(--l-violet-soft)", border: "1px solid var(--l-violet-border)", fontFamily: "var(--font-mono)", fontSize: "0.74rem", color: "var(--l-violet-text)", fontWeight: 600 }}>
                → llama-3.3-70b · verified allowlist
              </div>
            </div>

            {/* Bento Card 3: PharmaGraph + Safety (4 cols) */}
            <div className="bento-card bento-span-4">
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                  <div style={{ width: 42, height: 42, borderRadius: 12, background: "var(--l-rose-soft)", border: "1px solid var(--l-rose-border)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--l-rose-text)" }}>
                    <ShieldAlert size={20} />
                  </div>
                  <span className="mono-tag" style={{ color: "var(--l-rose-text)" }}>SAFETY GUARDRAIL</span>
                </div>
                <h3 style={{ fontFamily: "var(--font-display)", fontSize: "1.3rem", fontWeight: 700, margin: "0 0 8px" }}>
                  PharmaGraph & Substitutes
                </h3>
                <p style={{ color: "var(--l-text-secondary)", fontSize: "0.9rem", lineHeight: 1.6, margin: 0 }}>
                  Curated medicine → salt → condition knowledge graph catches dangerous drug interactions at billing time and suggests in-stock alternatives.
                </p>
              </div>
              <div style={{ marginTop: 18, display: "flex", gap: 6, flexWrap: "wrap", fontFamily: "var(--font-mono)", fontSize: "0.7rem" }}>
                <span style={{ padding: "4px 8px", borderRadius: 6, background: "var(--l-rose-soft)", color: "var(--l-rose-text)", fontWeight: 600 }}>40 DDI Pairs</span>
                <span style={{ padding: "4px 8px", borderRadius: 6, background: "var(--l-sky-soft)", color: "var(--l-sky-text)", fontWeight: 600 }}>162 Graph Edges</span>
              </div>
            </div>

            {/* Bento Card 4: Predictive Forecasting & Anomaly (4 cols) */}
            <div className="bento-card bento-span-4">
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                  <div style={{ width: 42, height: 42, borderRadius: 12, background: "var(--l-amber-soft)", border: "1px solid var(--l-amber-border)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--l-amber-text)" }}>
                    <TrendingUp size={20} />
                  </div>
                  <span className="mono-tag" style={{ color: "var(--l-amber-text)" }}>PREDICTIVE ML</span>
                </div>
                <h3 style={{ fontFamily: "var(--font-display)", fontSize: "1.3rem", fontWeight: 700, margin: "0 0 8px" }}>
                  Holt-Winters & Anomaly Watch
                </h3>
                <p style={{ color: "var(--l-text-secondary)", fontSize: "0.9rem", lineHeight: 1.6, margin: 0 }}>
                  14-day seasonal demand forecasting paired with IsolationForest pilferage/adjustment anomaly checks and supplier price spike alerts.
                </p>
              </div>
              <svg viewBox="0 0 220 44" style={{ width: "100%", height: 42, marginTop: 14 }}>
                <path
                  d="M4 36 C 32 34, 46 18, 72 24 C 98 30, 118 10, 148 16 C 174 22, 194 6, 216 8"
                  fill="none"
                  stroke="var(--l-amber)"
                  strokeWidth="2.8"
                  strokeLinecap="round"
                />
                <circle cx="216" cy="8" r="4.5" fill="var(--l-amber)" />
              </svg>
            </div>

            {/* Bento Card 5: Cold-Chain Monitoring (4 cols) */}
            <div className="bento-card bento-span-4">
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                  <div style={{ width: 42, height: 42, borderRadius: 12, background: "var(--l-sky-soft)", border: "1px solid var(--l-sky-border)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--l-sky-text)" }}>
                    <Snowflake size={20} />
                  </div>
                  <span className="mono-tag" style={{ color: "var(--l-sky-text)" }}>COLD CHAIN</span>
                </div>
                <h3 style={{ fontFamily: "var(--font-display)", fontSize: "1.3rem", fontWeight: 700, margin: "0 0 8px" }}>
                  Fridge Compliance & Alerts
                </h3>
                <p style={{ color: "var(--l-text-secondary)", fontSize: "0.9rem", lineHeight: 1.6, margin: 0 }}>
                  Track vaccine/insulin storage ranges, auto-log temperature excursions into TrustChain, and isolate affected batches before sale.
                </p>
              </div>
              <div style={{ marginTop: 18, padding: "10px 12px", borderRadius: 10, background: "var(--l-surface-inset)", border: "1px solid var(--l-sky-border)", display: "flex", justifyContent: "space-between", alignItems: "center", fontFamily: "var(--font-mono)", fontSize: "0.75rem" }}>
                <span style={{ color: "var(--l-sky-text)", fontWeight: 600 }}>SAFE: 2.0°C – 8.0°C</span>
                <span style={{ color: "var(--l-emerald-text)", fontWeight: 700 }}>4.2°C OK</span>
              </div>
            </div>

            {/* Bento Card 6: GST & Profit Optimizer (6 cols) */}
            <div className="bento-card bento-span-6">
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
                  <div style={{ width: 42, height: 42, borderRadius: 12, background: "var(--l-emerald-soft)", border: "1px solid var(--l-emerald-border)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--l-emerald-text)" }}>
                    <FileText size={20} />
                  </div>
                  <span className="mono-tag" style={{ color: "var(--l-emerald-text)" }}>FINANCE & GST ENGINE</span>
                </div>
                <h3 style={{ fontFamily: "var(--font-display)", fontSize: "1.3rem", fontWeight: 700, margin: "0 0 8px" }}>
                  CA-Ready GST PDF Reports & Profit Optimizer
                </h3>
                <p style={{ color: "var(--l-text-secondary)", fontSize: "0.9rem", lineHeight: 1.6, margin: 0 }}>
                  Slab-wise CGST/SGST and IGST summaries with supplier GSTIN state detection, ReportLab PDF export, and distributor margin compression rankings.
                </p>
              </div>
            </div>

            {/* Bento Card 7: Regional Pulse + Inter-Pharmacy Network (6 cols) */}
            <div className="bento-card bento-span-6">
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
                  <div style={{ width: 42, height: 42, borderRadius: 12, background: "var(--l-sky-soft)", border: "1px solid var(--l-sky-border)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--l-sky-text)" }}>
                    <Network size={20} />
                  </div>
                  <span className="mono-tag" style={{ color: "var(--l-sky-text)" }}>REGIONAL PULSE · k ≥ 3</span>
                </div>
                <h3 style={{ fontFamily: "var(--font-display)", fontSize: "1.3rem", fontWeight: 700, margin: "0 0 8px" }}>
                  Privacy-Preserving Health Signals & Peer Network
                </h3>
                <p style={{ color: "var(--l-text-secondary)", fontSize: "0.9rem", lineHeight: 1.6, margin: 0 }}>
                  Aggregates opted-in OTC surveillance signals without leaking customer or shop identity, and redistributes near-expiry surplus stock across local partner shops.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── FULL-WIDTH ARCHITECTURE & VIVA HIGHLIGHTS (#architecture) ── */}
      <section id="architecture" style={{ padding: "76px 0", borderTop: "1px solid var(--l-border)", background: "var(--l-bg-band)" }}>
        <div className="landing-container">
          <div style={{ textAlign: "center", maxWidth: 740, margin: "0 auto 44px" }}>
            <span className="mono-tag" style={{ color: "var(--l-sky-text)", fontWeight: 700, display: "block", marginBottom: 10 }}>
              SYSTEM ARCHITECTURE & RELIABILITY
            </span>
            <h2 style={{ fontFamily: "var(--font-display)", fontSize: "clamp(1.85rem, 3.4vw, 2.65rem)", fontWeight: 800, lineHeight: 1.14, letterSpacing: "-0.03em", margin: "0 0 12px" }}>
              Built like real healthcare infrastructure.
            </h2>
            <p style={{ color: "var(--l-text-secondary)", fontSize: "0.98rem", lineHeight: 1.6, margin: 0 }}>
              Verified across 474 automated backend tests, 22 frontend component tests, and 31 versioned Alembic migrations.
            </p>
          </div>

          <div className="arch-grid">
            {ARCHITECTURE_PILLARS.map((item) => {
              const Icon = item.icon;
              return (
                <div key={item.title} className="bento-card" style={{ padding: 22 }}>
                  <div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
                      <div style={{
                        width: 38,
                        height: 38,
                        borderRadius: 10,
                        background: `var(--l-${item.tone}-soft)`,
                        border: `1px solid var(--l-${item.tone}-border)`,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        color: `var(--l-${item.tone}-text)`,
                      }}>
                        <Icon size={18} />
                      </div>
                      <span className="mono-tag" style={{ color: `var(--l-${item.tone}-text)`, fontSize: "0.66rem", fontWeight: 700 }}>
                        {item.tag}
                      </span>
                    </div>
                    <h3 style={{ fontFamily: "var(--font-display)", fontSize: "1.08rem", fontWeight: 700, margin: "0 0 8px" }}>
                      {item.title}
                    </h3>
                    <p style={{ color: "var(--l-text-secondary)", fontSize: "0.84rem", lineHeight: 1.6, margin: 0 }}>
                      {item.desc}
                    </p>
                  </div>
                  <div style={{ marginTop: 18, paddingTop: 12, borderTop: "1px solid var(--l-border)", fontFamily: "var(--font-mono)", fontSize: "0.72rem", color: `var(--l-${item.tone}-text)`, fontWeight: 700 }}>
                    ✓ {item.metric}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ── FULL-WIDTH WORKFLOW + CTA + ATTRIBUTION (#workflow) ── */}
      <section id="workflow" style={{ padding: "76px 0 60px", borderTop: "1px solid var(--l-border)" }}>
        <div className="landing-container">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexWrap: "wrap", gap: 20, marginBottom: 34 }}>
            <div>
              <span className="mono-tag" style={{ color: "var(--l-emerald-text)", fontWeight: 700, display: "block", marginBottom: 8 }}>
                ONBOARDING WORKFLOW
              </span>
              <h2 style={{ fontFamily: "var(--font-display)", fontSize: "clamp(1.8rem, 3.2vw, 2.5rem)", fontWeight: 800, margin: 0, letterSpacing: "-0.03em" }}>
                From signup to AI billing in under 3 minutes.
              </h2>
            </div>
            <Link to="/register" className="landing-btn-secondary" style={{ padding: "10px 18px", fontSize: "0.85rem" }}>
              Try Registration Flow <ArrowRight size={15} />
            </Link>
          </div>

          <div className="workflow-grid" style={{ marginBottom: 32 }}>
            {STEPS.map((s) => (
              <div key={s.num} className="bento-card" style={{ padding: 24 }}>
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: "1.6rem", fontWeight: 700, color: "var(--l-emerald-text)" }}>
                      {s.num}
                    </span>
                    <span className="mono-tag" style={{ padding: "4px 9px", borderRadius: 6, background: "var(--l-surface-soft)", color: "var(--l-text-muted)", border: "1px solid var(--l-border)" }}>
                      {s.pill}
                    </span>
                  </div>
                  <h3 style={{ fontFamily: "var(--font-display)", fontSize: "1.18rem", fontWeight: 700, margin: "0 0 8px" }}>
                    {s.title}
                  </h3>
                  <p style={{ color: "var(--l-text-secondary)", fontSize: "0.88rem", lineHeight: 1.6, margin: 0 }}>
                    {s.desc}
                  </p>
                </div>
              </div>
            ))}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 18 }}>
            <div className="bento-card" style={{ background: "var(--l-cta-bg)", borderColor: "var(--l-emerald-border)" }}>
              <div>
                <span className="mono-tag" style={{ color: "var(--l-emerald-text)", fontWeight: 700, display: "block", marginBottom: 10 }}>
                  LIVE DEMONSTRATION READY
                </span>
                <h2 style={{ fontFamily: "var(--font-display)", fontSize: "clamp(1.65rem, 2.8vw, 2.2rem)", fontWeight: 800, margin: "0 0 10px", letterSpacing: "-0.025em" }}>
                  Ready to explore the live system?
                </h2>
                <p style={{ color: "var(--l-text-secondary)", fontSize: "0.94rem", lineHeight: 1.6, margin: "0 0 22px" }}>
                  Sign in as Shop Owner or Staff to test POS interaction alerts, upload invoices, inspect TrustChain hashes, or chat with PharmaCopilot.
                </p>
              </div>
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                <Link to="/login" className="landing-btn-primary">
                  Open Live Workspace <ArrowRight size={16} />
                </Link>
                <Link to="/register" className="landing-btn-secondary">
                  Register New Shop
                </Link>
              </div>
            </div>

            <div className="bento-card">
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
                  <div style={{ width: 46, height: 46, borderRadius: 14, background: "var(--l-emerald-soft)", border: "1px solid var(--l-emerald-border)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--l-emerald-text)" }}>
                    <Code2 size={22} />
                  </div>
                  <div>
                    <div className="mono-tag" style={{ color: "var(--l-text-muted)" }}>ARCHITECTED & BUILT BY</div>
                    <div style={{ fontFamily: "var(--font-display)", fontSize: "1.35rem", fontWeight: 800, color: "var(--l-text-primary)" }}>
                      Yash Gupta
                    </div>
                  </div>
                </div>
                <p style={{ color: "var(--l-text-secondary)", fontSize: "0.9rem", lineHeight: 1.65, margin: "0 0 20px" }}>
                  Full-stack multi-tenant healthcare platform uniting OCR document pipelines, PharmaGraph clinical guardrails, time-series demand forecasting, and privacy-preserving regional surveillance.
                </p>
              </div>
              <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                <span className="mono-tag" style={{ padding: "6px 12px", borderRadius: 9999, background: "var(--l-surface-soft)", border: "1px solid var(--l-border)", color: "var(--l-text-secondary)" }}>
                  <Layers size={12} style={{ verticalAlign: "middle", marginRight: 6 }} />
                  FastAPI · React · Applied AI
                </span>
                <span className="mono-tag" style={{ padding: "6px 12px", borderRadius: 9999, background: "var(--l-emerald-soft)", border: "1px solid var(--l-emerald-border)", color: "var(--l-emerald-text)", fontWeight: 700 }}>
                  <Cpu size={12} style={{ verticalAlign: "middle", marginRight: 6 }} />
                  474+ Automated Checks
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── FULL-WIDTH FOOTER ── */}
      <footer style={{ borderTop: "1px solid var(--l-border)", padding: "24px 0", background: "var(--l-topbar-bg)" }}>
        <div className="landing-container" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 800, color: "var(--l-emerald-text)", fontFamily: "var(--font-display)" }}>
            <Hexagon size={18} />
            PharmOS
          </div>
          <div className="mono-tag" style={{ color: "var(--l-text-muted)" }}>
            © 2026 PharmOS · Intelligent Multi-Tenant Pharmacy Operating System
          </div>
        </div>
      </footer>
    </div>
  );
}
