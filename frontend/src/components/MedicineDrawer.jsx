import { motion, AnimatePresence } from "framer-motion";
import { X, Package, Activity, AlertTriangle, ShieldCheck, HeartPulse } from "lucide-react";

export default function MedicineDrawer({ medicine, isOpen, onClose }) {
  return (
    <AnimatePresence>
      {isOpen && medicine && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            style={{
              position: "fixed", top: 0, left: 0, width: "100vw", height: "100vh",
              background: "rgba(0,0,0,0.3)", backdropFilter: "blur(4px)",
              zIndex: 999998
            }}
            onClick={onClose}
          />
          <motion.div
            initial={{ x: "100%", opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: "100%", opacity: 0 }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
            style={{
              position: "fixed", top: 0, right: 0, width: "400px", maxWidth: "100vw", height: "100vh",
              background: "var(--bg-surface)", boxShadow: "-10px 0 30px rgba(0,0,0,0.1)",
              zIndex: 999999, display: "flex", flexDirection: "column",
              borderLeft: "1px solid var(--border-subtle)"
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "20px 24px", borderBottom: "1px solid var(--border-subtle)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <div style={{ width: 40, height: 40, borderRadius: 10, background: "var(--primary-50)", color: "var(--primary-600)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <HeartPulse size={24} />
                </div>
                <div>
                  <h2 style={{ margin: 0, fontSize: "1.2rem", color: "var(--text-main)" }}>{medicine.name}</h2>
                  <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>ID: {medicine.id || medicine.medicine_id}</span>
                </div>
              </div>
              <button onClick={onClose} style={{ background: "transparent", border: "none", cursor: "pointer", color: "var(--text-muted)" }}>
                <X size={24} />
              </button>
            </div>

            <div style={{ padding: "24px", overflowY: "auto", flex: 1, display: "flex", flexDirection: "column", gap: 24 }}>
              
              <div style={{ display: "flex", gap: 16 }}>
                <div style={{ flex: 1, background: "var(--bg-app)", padding: 16, borderRadius: "var(--radius-lg)", border: "1px solid var(--border-subtle)" }}>
                  <div style={{ color: "var(--text-muted)", fontSize: "12px", marginBottom: 4, display: "flex", alignItems: "center", gap: 6 }}><Package size={14} /> Current Stock</div>
                  <div style={{ fontSize: "24px", fontWeight: 700, color: "var(--text-main)" }}>{medicine.current_stock ?? medicine.total_stock ?? "-"}</div>
                </div>
                <div style={{ flex: 1, background: "var(--bg-app)", padding: 16, borderRadius: "var(--radius-lg)", border: "1px solid var(--border-subtle)" }}>
                  <div style={{ color: "var(--text-muted)", fontSize: "12px", marginBottom: 4, display: "flex", alignItems: "center", gap: 6 }}><AlertTriangle size={14} /> Threshold</div>
                  <div style={{ fontSize: "24px", fontWeight: 700, color: "var(--text-main)" }}>{medicine.low_stock_threshold ?? "-"}</div>
                </div>
              </div>

              <div>
                <h3 style={{ fontSize: "14px", color: "var(--text-main)", marginBottom: 12, display: "flex", alignItems: "center", gap: 6 }}><Activity size={16} /> Details</h3>
                <div style={{ background: "var(--bg-app)", borderRadius: "var(--radius-lg)", border: "1px solid var(--border-subtle)", overflow: "hidden" }}>
                  {[
                    { label: "Manufacturer", value: medicine.manufacturer || "N/A" },
                    { label: "Category", value: medicine.category || "N/A" },
                    { label: "Location", value: medicine.location || "N/A" },
                    { label: "Composition", value: medicine.composition || "N/A" },
                    { label: "Lead Time", value: medicine.lead_time_days ? `${medicine.lead_time_days} days` : "N/A" }
                  ].map((row, i) => (
                    <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "12px 16px", borderBottom: i < 4 ? "1px solid var(--border-subtle)" : "none" }}>
                      <span style={{ color: "var(--text-muted)", fontSize: "13px" }}>{row.label}</span>
                      <span style={{ color: "var(--text-main)", fontSize: "13px", fontWeight: 500, textAlign: "right" }}>{row.value}</span>
                    </div>
                  ))}
                </div>
              </div>

              {medicine.tags && medicine.tags.length > 0 && (
                <div>
                  <h3 style={{ fontSize: "14px", color: "var(--text-main)", marginBottom: 12, display: "flex", alignItems: "center", gap: 6 }}><ShieldCheck size={16} /> Tags</h3>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                    {medicine.tags.map(t => (
                      <span key={t} style={{ background: "var(--primary-50)", color: "var(--primary-600)", padding: "4px 10px", borderRadius: "100px", fontSize: "12px", fontWeight: 600 }}>
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
            
            <div style={{ padding: "20px 24px", borderTop: "1px solid var(--border-subtle)", background: "var(--bg-app)" }}>
              <button onClick={onClose} className="btn btn-primary" style={{ width: "100%" }}>Done</button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
