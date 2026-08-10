import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

export default function ConfettiExplosion({ show, onComplete }) {
  const [particles, setParticles] = useState([]);

  useEffect(() => {
    if (show) {
      const colors = ["var(--primary-500)", "var(--accent-500)", "var(--success-500)", "var(--warning-500)"];
      const newParticles = Array.from({ length: 40 }).map((_, i) => ({
        id: i,
        x: (Math.random() - 0.5) * 300,
        y: (Math.random() - 0.5) * 300 - 100,
        rotation: Math.random() * 360,
        scale: Math.random() * 0.5 + 0.5,
        color: colors[Math.floor(Math.random() * colors.length)],
        delay: Math.random() * 0.1
      }));
      setParticles(newParticles);
      
      const timer = setTimeout(() => {
        if (onComplete) onComplete();
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, [show, onComplete]);

  return (
    <div style={{ position: "absolute", top: "50%", left: "50%", pointerEvents: "none", zIndex: 9999 }}>
      <AnimatePresence>
        {show && particles.map(p => (
          <motion.div
            key={p.id}
            initial={{ x: 0, y: 0, scale: 0, opacity: 1, rotate: 0 }}
            animate={{ 
              x: p.x, 
              y: p.y, 
              scale: p.scale, 
              opacity: 0,
              rotate: p.rotation
            }}
            exit={{ opacity: 0 }}
            transition={{ duration: 1, delay: p.delay, ease: "easeOut" }}
            style={{
              position: "absolute",
              width: 8, height: 8,
              background: p.color,
              borderRadius: Math.random() > 0.5 ? "50%" : "2px"
            }}
          />
        ))}
      </AnimatePresence>
    </div>
  );
}
