import React from "react";
import { motion } from "framer-motion";

export default function ActivityRings({ rings, size = 180, strokeWidth = 14 }) {
  const center = size / 2;

  return (
    <div style={{ position: "relative", width: size, height: size, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        {rings.map((ring, index) => {
          const radius = center - strokeWidth - (index * (strokeWidth + 4));
          const circumference = 2 * Math.PI * radius;
          const strokeDashoffset = circumference - ((ring.percentage > 100 ? 100 : ring.percentage) / 100) * circumference;
          
          return (
            <g key={index}>
              {/* Background Track */}
              <circle
                cx={center}
                cy={center}
                r={radius}
                fill="none"
                stroke={ring.color}
                strokeWidth={strokeWidth}
                opacity={0.2}
              />
              {/* Animated Progress Ring */}
              <motion.circle
                cx={center}
                cy={center}
                r={radius}
                fill="none"
                stroke={ring.color}
                strokeWidth={strokeWidth}
                strokeLinecap="round"
                strokeDasharray={circumference}
                initial={{ strokeDashoffset: circumference }}
                animate={{ strokeDashoffset }}
                transition={{ duration: 1.5, ease: "easeOut", delay: index * 0.2 }}
                style={{
                  filter: ring.percentage >= 100 ? `drop-shadow(0 0 6px ${ring.color})` : "none"
                }}
              />
            </g>
          );
        })}
      </svg>
      {/* Tooltip Overlay */}
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", pointerEvents: "none" }}>
        <span style={{ fontSize: "14px", fontWeight: 700, color: "var(--text-main)" }}>Daily Pulse</span>
      </div>
    </div>
  );
}
