import { motion } from "framer-motion";

export default function EmptyState({ icon: Icon, title, message }) {
  return (
    <motion.div 
      initial={{ opacity: 0, scale: 0.95, y: 10 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ duration: 0.3, type: "spring", stiffness: 300, damping: 25 }}
      style={{
        display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
        padding: "64px 24px", textAlign: "center",
        background: "var(--bg-app)", borderRadius: "var(--radius-xl)", border: "1px dashed var(--border-strong)",
        margin: "24px 0"
      }}
    >
      <div style={{
        width: 80, height: 80, borderRadius: "50%", background: "var(--primary-50)",
        display: "flex", alignItems: "center", justifyContent: "center",
        color: "var(--primary-500)", marginBottom: 24,
        boxShadow: "0 10px 30px rgba(20, 184, 166, 0.15)"
      }}>
        {Icon && <Icon size={40} strokeWidth={1.5} />}
      </div>
      <h3 style={{ fontSize: "1.25rem", color: "var(--text-main)", marginBottom: 8, fontWeight: 700 }}>
        {title}
      </h3>
      <p style={{ color: "var(--text-secondary)", maxWidth: 300, lineHeight: 1.6, margin: 0 }}>
        {message}
      </p>
    </motion.div>
  );
}
