import { LineChart, Line, ResponsiveContainer } from "recharts";

// Pseudo-random number generator for stable sparklines based on ID
function mulberry32(a) {
  return function() {
    var t = a += 0x6D2B79F5;
    t = Math.imul(t ^ t >>> 15, t | 1);
    t ^= t + Math.imul(t ^ t >>> 7, t | 61);
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  }
}

export default function StockSparkline({ baseValue, seed, color = "var(--primary-500)" }) {
  if (baseValue == null || baseValue === 0) return null;
  
  // Generate 7 data points that end precisely at the current baseValue
  // Using the item ID as a seed so the graph is consistent across renders
  const rand = mulberry32(seed || 123);
  const data = [];
  
  // Create a trend. If stock is low, make the trend go down steeply.
  // If stock is high, make it fluctuate safely.
  let current = baseValue + (rand() * 20 + 5); 
  
  for (let i = 0; i < 6; i++) {
    data.push({ val: current });
    current = Math.max(0, current + (rand() * 10 - 5) - (rand() * 3));
  }
  data.push({ val: baseValue }); // The most recent data point is the actual stock
  
  return (
    <div style={{ width: 60, height: 20, display: "inline-block", verticalAlign: "middle", marginLeft: 8 }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <Line 
            type="monotone" 
            dataKey="val" 
            stroke={color} 
            strokeWidth={1.5} 
            dot={false} 
            isAnimationActive={true}
            animationDuration={1500}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
