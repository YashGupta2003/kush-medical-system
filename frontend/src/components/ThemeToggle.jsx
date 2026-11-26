import { Moon, Sun } from "lucide-react";
import { motion } from "framer-motion";
import { useTheme } from "../utils/theme.js";

export default function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === "dark";

  return (
    <motion.button
      onClick={toggleTheme}
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.95 }}
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        width: 36,
        height: 36,
        borderRadius: "50%",
        background: "var(--bg-surface)",
        border: "1px solid var(--border-subtle)",
        color: "var(--text-main)",
        cursor: "pointer",
        boxShadow: "0 2px 10px rgba(0,0,0,0.03)",
      }}
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      title={isDark ? "Switch to light mode" : "Switch to dark mode"}
    >
      {isDark ? <Sun size={18} /> : <Moon size={18} />}
    </motion.button>
  );
}
