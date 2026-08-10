import { useEffect, useState } from "react";
import { Pill, Syringe, Activity, Plus, ShieldPlus, Stethoscope, HeartPulse, Dna } from "lucide-react";

const ICONS = [Pill, Syringe, Activity, Plus, ShieldPlus, Stethoscope, HeartPulse, Dna];

export default function MedicalBackground() {
  const [particles, setParticles] = useState([]);

  useEffect(() => {
    // Generate static particles on mount
    const items = Array.from({ length: 30 }).map((_, i) => {
      // Create a sense of depth: foreground is larger/faster, background is smaller/slower
      const isForeground = Math.random() > 0.5;
      return {
        id: i,
        Icon: ICONS[Math.floor(Math.random() * ICONS.length)],
        left: `${Math.random() * 95}vw`,
        animationDuration: `${(isForeground ? 15 : 30) + Math.random() * 20}s`,
        animationDelay: `-${Math.random() * 30}s`,
        opacity: isForeground ? 0.08 + Math.random() * 0.05 : 0.03 + Math.random() * 0.03,
        size: isForeground ? 35 + Math.random() * 40 : 15 + Math.random() * 20,
        rotationStart: Math.random() * 360,
        rotationEnd: Math.random() * 360 + (Math.random() > 0.5 ? 360 : -360),
        // Mix between primary teal and accent coral/amber
        color: Math.random() > 0.2 ? "var(--primary-500)" : "var(--accent-500)"
      };
    });
    setParticles(items);
  }, []);

  return (
    <div style={{
      position: "fixed", top: 0, left: 0, width: "100vw", height: "100vh",
      overflow: "hidden", zIndex: 0, pointerEvents: "none"
    }}>
      <style>{`
        @keyframes floatDown {
          0% { transform: translateY(-15vh) rotate(var(--rot-start)); }
          100% { transform: translateY(115vh) rotate(var(--rot-end)); }
        }
        @keyframes pulseGlow1 {
          0%, 100% { transform: scale(1) translate(0, 0); opacity: 0.12; }
          50% { transform: scale(1.1) translate(40px, -40px); opacity: 0.18; }
        }
        @keyframes pulseGlow2 {
          0%, 100% { transform: scale(1) translate(0, 0); opacity: 0.08; }
          50% { transform: scale(1.15) translate(-40px, 30px); opacity: 0.15; }
        }
      `}</style>
      
      {/* Ambient Glowing Orbs for a premium mesh-gradient feel */}
      <div style={{
        position: "absolute", top: "-10%", left: "-5%", width: "50vw", height: "50vw",
        background: "radial-gradient(circle, var(--primary-400) 0%, transparent 70%)",
        filter: "blur(100px)", opacity: 0.12,
        animation: "pulseGlow1 20s ease-in-out infinite",
        borderRadius: "50%"
      }} />
      <div style={{
        position: "absolute", bottom: "-20%", right: "-10%", width: "60vw", height: "60vw",
        background: "radial-gradient(circle, var(--accent-400) 0%, transparent 70%)",
        filter: "blur(120px)", opacity: 0.08,
        animation: "pulseGlow2 25s ease-in-out infinite",
        borderRadius: "50%"
      }} />

      {/* Floating Medical Particles */}
      {particles.map((p) => {
        const IconComponent = p.Icon;
        return (
          <div
            key={p.id}
            style={{
              position: "absolute",
              left: p.left,
              top: 0,
              opacity: p.opacity,
              color: p.color,
              filter: "drop-shadow(0px 4px 12px rgba(20, 184, 166, 0.25))",
              animation: `floatDown ${p.animationDuration} linear infinite`,
              animationDelay: p.animationDelay,
              "--rot-start": `${p.rotationStart}deg`,
              "--rot-end": `${p.rotationEnd}deg`,
            }}
          >
            <IconComponent size={p.size} />
          </div>
        );
      })}
    </div>
  );
}
