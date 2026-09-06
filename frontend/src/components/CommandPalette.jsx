import { useEffect, useState, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search, Command, ArrowRight } from "lucide-react";
import { useNavigate } from "react-router-dom";
const MODULES = [
  { id: "analytics", name: "Analytics Dashboard", path: "/analytics", icon: "📊" },
  { id: "central", name: "Central Command", path: "/", icon: "🔍" },
  { id: "copilot", name: "PharmaCopilot", path: "/copilot", icon: "🤖" },
  { id: "predictive", name: "Predictive Orders", path: "/predictive", icon: "🔮" },
  { id: "pos", name: "Point of Sale", path: "/pos", icon: "🛒" },
  { id: "bills", name: "Bill History", path: "/bills", icon: "🧾" },
  { id: "upload", name: "Upload Bill", path: "/upload", icon: "📤" },
  { id: "stock", name: "Stock Management", path: "/stock", icon: "📦" },
  { id: "expiry", name: "Expiry Tracking", path: "/expiry", icon: "⏳" },
  { id: "substitutes", name: "Medicine Substitutes", path: "/substitutes", icon: "💊" },
  { id: "scan", name: "Barcode Scanner", path: "/scan", icon: "📷" },
  { id: "gst", name: "GST Report", path: "/gst", icon: "📑" },
  { id: "audit", name: "Audit Trail", path: "/audit", icon: "🛡️" },
  { id: "trust", name: "Trust Score", path: "/trust-score", icon: "⭐" },
  { id: "surveillance", name: "Surveillance", path: "/surveillance", icon: "👁️" },
  { id: "cold-chain", name: "Cold Chain", path: "/cold-chain", icon: "❄️" },
  { id: "customers", name: "Customers", path: "/customers", icon: "👥" },
  { id: "network", name: "Network", path: "/network", icon: "🌐" },
  { id: "integrity", name: "Network Integrity", path: "/network-integrity", icon: "🛡️" },

];

export default function CommandPalette() {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const navigate = useNavigate();
  const inputRef = useRef(null);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setIsOpen((prev) => !prev);
        setSearch("");
        setSelectedIndex(0);
      }
      if (e.key === "Escape") setIsOpen(false);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const filtered = MODULES.filter((m) =>
    m.name.toLowerCase().includes(search.toLowerCase()) || 
    m.id.toLowerCase().includes(search.toLowerCase())
  );

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen]);

  const handleSelect = (path) => {
    setIsOpen(false);
    navigate(path);
  };

  const handleKeyDown = (e) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % filtered.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + filtered.length) % filtered.length);
    } else if (e.key === "Enter" && filtered.length > 0) {
      handleSelect(filtered[selectedIndex].path);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div 
          style={{
            position: "fixed", top: 0, left: 0, width: "100vw", height: "100vh",
            background: "rgba(0,0,0,0.5)", backdropFilter: "blur(4px)",
            zIndex: 99999, display: "flex", justifyContent: "center", paddingTop: "15vh"
          }}
          onClick={() => setIsOpen(false)}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -10 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            onClick={(e) => e.stopPropagation()}
            style={{
              background: "var(--bg-surface)",
              width: "100%", maxWidth: "600px",
              borderRadius: "var(--radius-lg)",
              boxShadow: "0 20px 60px rgba(0,0,0,0.15)",
              overflow: "hidden", border: "1px solid var(--border-strong)",
              display: "flex", flexDirection: "column"
            }}
          >
            <div style={{ display: "flex", alignItems: "center", padding: "16px", borderBottom: "1px solid var(--border-subtle)" }}>
              <Search size={20} style={{ color: "var(--text-muted)", marginRight: 12 }} />
              <input
                ref={inputRef}
                value={search}
                onChange={(e) => { setSearch(e.target.value); setSelectedIndex(0); }}
                onKeyDown={handleKeyDown}
                placeholder="Search modules or jump to page..."
                style={{
                  flex: 1, border: "none", outline: "none", background: "transparent",
                  fontSize: "1.2rem", color: "var(--text-main)", fontWeight: 500
                }}
              />
              <div style={{ display: "flex", alignItems: "center", gap: 4, color: "var(--text-muted)", fontSize: "12px", background: "var(--bg-app)", padding: "4px 8px", borderRadius: 4, fontWeight: 600 }}>
                <Command size={14} /> K
              </div>
            </div>
            
            <div style={{ maxHeight: "400px", overflowY: "auto", padding: "8px" }}>
              {filtered.length === 0 ? (
                <div style={{ padding: "32px", textAlign: "center", color: "var(--text-muted)" }}>
                  No matching modules found.
                </div>
              ) : (
                filtered.map((m, idx) => {
                  const isSelected = idx === selectedIndex;
                  return (
                    <div
                      key={m.id}
                      onClick={() => handleSelect(m.path)}
                      onMouseEnter={() => setSelectedIndex(idx)}
                      style={{
                        padding: "12px 16px", display: "flex", alignItems: "center", gap: 12,
                        cursor: "pointer", borderRadius: "var(--radius-md)",
                        background: isSelected ? "var(--primary-50)" : "transparent",
                        color: isSelected ? "var(--primary-600)" : "var(--text-main)",
                        transition: "background 0.2s"
                      }}
                    >
                      <span style={{ fontSize: "20px" }}>{m.icon}</span>
                      <span style={{ flex: 1, fontWeight: isSelected ? 600 : 500 }}>{m.name}</span>
                      {isSelected && <ArrowRight size={16} />}
                    </div>
                  );
                })
              )}
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
