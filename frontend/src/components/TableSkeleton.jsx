import { motion } from "framer-motion";

export default function TableSkeleton({ rows = 5, columns = 4 }) {
  return (
    <div style={{ width: "100%", overflowX: "auto" }}>
      <table className="table" style={{ width: "100%", margin: 0 }}>
        <thead>
          <tr>
            {Array.from({ length: columns }).map((_, i) => (
              <th key={i} style={{ padding: "12px" }}>
                <div style={{ height: "14px", width: "60%", background: "var(--bg-muted)", borderRadius: "4px" }} />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: rows }).map((_, r) => (
            <tr key={r}>
              {Array.from({ length: columns }).map((_, c) => (
                <td key={c} style={{ padding: "16px 12px", borderBottom: "1px solid var(--border-subtle)" }}>
                  <motion.div 
                    initial={{ opacity: 0.5 }}
                    animate={{ opacity: 1 }}
                    transition={{ repeat: Infinity, duration: 0.8, repeatType: "reverse", ease: "easeInOut" }}
                    style={{ 
                      height: "16px", 
                      width: c === 0 ? "80%" : "50%", 
                      background: "var(--border-subtle)", 
                      borderRadius: "4px" 
                    }} 
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
