import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";

export default function ThemeToggle() {
  const [isDark, setIsDark] = useState(() => {
    return document.documentElement.getAttribute("data-theme") === "dark";
  });

  const toggleTheme = (e) => {
    const nextIsDark = !isDark;
    
    if (!document.startViewTransition) {
      document.documentElement.setAttribute("data-theme", nextIsDark ? "dark" : "light");
      setIsDark(nextIsDark);
      return;
    }

    const x = e.clientX;
    const y = e.clientY;
    const endRadius = Math.hypot(
      Math.max(x, window.innerWidth - x),
      Math.max(y, window.innerHeight - y)
    );

    const transition = document.startViewTransition(() => {
      document.documentElement.setAttribute("data-theme", nextIsDark ? "dark" : "light");
      setIsDark(nextIsDark);
    });

    transition.ready.then(() => {
      const clipPath = [
        `circle(0px at ${x}px ${y}px)`,
        `circle(${endRadius}px at ${x}px ${y}px)`
      ];

      document.documentElement.animate(
        {
          clipPath: nextIsDark ? clipPath : [...clipPath].reverse()
        },
        {
          duration: 500,
          easing: "ease-in-out",
          pseudoElement: nextIsDark ? "::view-transition-new(root)" : "::view-transition-old(root)"
        }
      );
    });
  };

  return (
    <motion.button 
      onClick={toggleTheme}
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.95 }}
      style={{
        display: "flex", alignItems: "center", justifyContent: "center",
        width: 36, height: 36, borderRadius: "50%",
        background: "var(--bg-surface)", border: "1px solid var(--border-subtle)",
        color: "var(--text-main)", cursor: "pointer",
        boxShadow: "0 2px 10px rgba(0,0,0,0.03)"
      }}
      aria-label="Toggle Theme"
    >
      {isDark ? <Sun size={18} /> : <Moon size={18} />}
    </motion.button>
  );
}
