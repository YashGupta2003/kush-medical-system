import React, { useEffect, useState, useMemo } from "react";
import { motion } from "framer-motion";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  PieChart, Pie, Cell, Legend, AreaChart, Area
} from "recharts";
import { 
  Activity, TrendingUp, Flame, Package, DollarSign, Clock, AlertTriangle, FileText,
  TrendingDown, ShoppingCart, Zap, Calendar, Sparkles, PieChart as PieIcon, BarChart2,
  Users
} from "lucide-react";
import { api } from "../api/client.js";
import { useAuth } from "../auth/AuthContext.jsx";
import AnimatedNumber from "../components/AnimatedNumber.jsx";
import ActivityRings from "../components/ActivityRings.jsx";

const PIE_COLORS = ["var(--primary-500)", "var(--success-text)", "var(--warning-text)", "var(--danger-text)", "var(--info-text)", "var(--accent-500)", "#a3e635", "#f43f5e"];

const StatCard = ({ title, value, icon: Icon, trend, trendUp, subtitle, iconBg, iconColor, delay = 0, isMoney = false }) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.4, delay }}
    style={{
      background: "var(--bg-surface)",
      border: "1px solid var(--border-light)",
      borderRadius: "20px",
      padding: "24px",
      display: "flex",
      flexDirection: "column",
      gap: "12px",
      position: "relative",
      overflow: "hidden",
      boxShadow: "0 10px 15px -3px rgba(0, 0, 0, 0.05), 0 4px 6px -4px rgba(0, 0, 0, 0.05)",
    }}
  >
    <div style={{ position: "absolute", top: "-10px", right: "-10px", opacity: 0.03, transform: "scale(2.5)" }}>
      <Icon size={64} />
    </div>
    
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
      <span style={{ color: "var(--text-muted)", fontSize: "15px", fontWeight: 600 }}>{title}</span>
      <div style={{ 
        padding: "10px", borderRadius: "12px", display: "flex", alignItems: "center", justifyContent: "center",
        background: iconBg || "var(--primary-50)", color: iconColor || "var(--primary-600)"
      }}>
        <Icon size={20} />
      </div>
    </div>
    
    <div style={{ display: "flex", alignItems: "baseline", gap: "10px", marginTop: "4px" }}>
      <span style={{ fontSize: "32px", fontWeight: 800, color: "var(--text-color)", letterSpacing: "-0.5px" }}>
        <AnimatedNumber value={value || 0} prefix={isMoney ? "₹" : ""} />
      </span>
      {trend && (
        <span style={{ 
          fontSize: "13px", fontWeight: 700,
          color: trendUp ? "var(--success-text)" : "var(--danger-text)",
          display: "flex", alignItems: "center", gap: "4px",
          background: trendUp ? "var(--success-bg)" : "var(--danger-bg)",
          padding: "4px 8px", borderRadius: "20px"
        }}>
          {trendUp ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
          {trend}
        </span>
      )}
    </div>
    
    {subtitle && (
      <span style={{ fontSize: "13px", color: "var(--text-muted)", fontWeight: 500 }}>{subtitle}</span>
    )}
  </motion.div>
);

function formatMoney(n) {
  if (n == null) return "₹0";
  return "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

export default function Analytics() {
  const { user } = useAuth();
  const [overview, setOverview] = useState(null);
  const [monthlySpend, setMonthlySpend] = useState([]);
  const [distributorData, setDistributorData] = useState([]);
  const [priceChanges, setPriceChanges] = useState([]);
  const [topSpend, setTopSpend] = useState([]);
  const [topSelling, setTopSelling] = useState([]);
  const [priceWindow, setPriceWindow] = useState(90);
  const [loading, setLoading] = useState(true);

  function refresh() {
    setLoading(true);
    Promise.all([
      api.getAnalyticsOverview(),
      api.getMonthlySpend(6),
      api.getDistributorBreakdown(),
      api.getPriceChanges(priceWindow, 8),
      api.getTopMedicinesBySpend(undefined, undefined, 8),
      api.getTopSelling(30, 8),
    ]).then(([ov, ms, db, pc, ts, tsell]) => {
      setOverview(ov);
      setMonthlySpend(ms);
      setDistributorData(db);
      setPriceChanges(pc);
      setTopSpend(ts);
      setTopSelling(tsell);
      setLoading(false);
    });
  }

  useEffect(() => { refresh(); /* eslint-disable-next-line */ }, [priceWindow]);

  if (loading && !overview) {
    return (
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "70vh" }}>
        <motion.div animate={{ rotate: 360, scale: [1, 1.1, 1] }} transition={{ repeat: Infinity, duration: 1.5, ease: "easeInOut" }}>
          <Activity size={40} color="var(--primary-600)" />
        </motion.div>
      </div>
    );
  }

  const ov = overview || {};
  
  return (
    <motion.div 
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.3 }}
      style={{ padding: "32px", width: "100%", maxWidth: "100%", margin: "0 auto", paddingBottom: "100px" }}
    >
      
      {/* Header section */}
      <div style={{ marginBottom: "32px", display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: "24px" }}>
        <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
          <h1 style={{ fontSize: "36px", fontWeight: 800, color: "var(--text-color)", marginBottom: "12px", letterSpacing: "-1px" }}>
            Analytics & Intelligence <Sparkles size={28} color="var(--primary-500)" style={{ display: "inline", verticalAlign: "middle", marginBottom: "4px" }} />
          </h1>
          <p style={{ color: "var(--text-muted)", fontSize: "16px", fontWeight: 500 }}>
            Live business intelligence, pulled from your bills, stock, sales, and price history.
          </p>
        </motion.div>

        {ov.this_month_spend != null && (
          <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.5, delay: 0.2 }}>
            <div style={{ display: "flex", gap: "24px", alignItems: "center", background: "var(--bg-surface)", padding: "16px 24px", borderRadius: "20px", border: "1px solid var(--border-light)" }}>
              <ActivityRings 
                size={80} strokeWidth={8}
                rings={[
                  { color: "var(--success-text)", percentage: 85, label: "Revenue" },
                  { color: "var(--primary-500)", percentage: 60, label: "Pending Bills" },
                  { color: "var(--warning-text)", percentage: 30, label: "Low Stock" }
                ]} 
              />
              <div style={{ display: "flex", flexDirection: "column", gap: "10px", fontSize: "13px", fontWeight: 600, color: "var(--text-muted)" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}><span style={{ width: 10, height: 10, borderRadius: "50%", background: "var(--success-text)" }} /> Revenue Goal</div>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}><span style={{ width: 10, height: 10, borderRadius: "50%", background: "var(--primary-500)" }} /> Pending Bills</div>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}><span style={{ width: 10, height: 10, borderRadius: "50%", background: "var(--warning-text)" }} /> Low Stock Alert</div>
              </div>
            </div>
          </motion.div>
        )}
      </div>

      {/* Top Stats Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "24px", marginBottom: "32px" }}>
        <StatCard 
          title="This month's spend" 
          value={ov.this_month_spend} 
          isMoney
          icon={DollarSign} 
          trend={ov.spend_change_pct != null ? `${Math.abs(ov.spend_change_pct).toFixed(1)}%` : null}
          trendUp={ov.spend_change_pct < 0}
          subtitle={ov.spend_change_pct == null ? "No data for last month" : `vs last month`}
          iconBg="var(--primary-50)" iconColor="var(--primary-600)"
          delay={0.1}
        />
        
        <StatCard 
          title="Stock value on hand" 
          value={ov.stock_value} 
          isMoney
          icon={Package} 
          subtitle="Estimated net value"
          iconBg="var(--success-bg)" iconColor="var(--success-text)"
          delay={0.2}
        />
        
        <StatCard 
          title="Low stock items" 
          value={ov.low_stock_count} 
          icon={AlertTriangle} 
          subtitle="Requires attention"
          iconBg="var(--warning-bg)" iconColor="var(--warning-text)"
          trend={ov.low_stock_count > 0 ? "Warning" : null}
          trendUp={false}
          delay={0.3}
        />
        
        <StatCard 
          title="Distributors Used" 
          value={ov.distributors_used_this_month} 
          icon={Users} 
          subtitle="Active suppliers this month"
          iconBg="var(--info-bg)" iconColor="var(--info-text)"
          delay={0.4}
        />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr", gap: "32px", marginBottom: "32px" }}>
        
        {/* Left Column Area */}
        <div style={{ display: "flex", flexDirection: "column", gap: "32px" }}>
          
          {/* Spend Chart */}
          <motion.div
            initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.4 }}
            style={{
              background: "var(--bg-surface)", border: "1px solid var(--border-light)",
              borderRadius: "20px", padding: "24px"
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "24px" }}>
               <h3 style={{ fontSize: "18px", fontWeight: 700, color: "var(--text-color)", display: "flex", alignItems: "center", gap: "8px", margin: 0 }}>
                 <Calendar size={20} color="var(--primary-500)"/> Monthly Purchase Spend (last 6 months)
               </h3>
            </div>
            {monthlySpend.length > 0 ? (
              <div style={{ height: "300px", width: "100%" }}>
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={monthlySpend.slice().reverse()} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="colorSpend" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="var(--primary-500)" stopOpacity={0.3}/>
                        <stop offset="95%" stopColor="var(--primary-500)" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border-light)" />
                    <XAxis dataKey="label" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: "var(--text-muted)" }} dy={10} />
                    <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: "var(--text-muted)" }} tickFormatter={(val) => `₹${(val/1000)}k`} />
                    <Tooltip formatter={(v) => formatMoney(v)} contentStyle={{ borderRadius: "12px", border: "none", boxShadow: "var(--shadow-lg)" }} />
                    <Area type="monotone" dataKey="total_spend" stroke="var(--primary-500)" strokeWidth={3} fillOpacity={1} fill="url(#colorSpend)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p style={{ color: "var(--text-muted)" }}>No purchase data available.</p>
            )}
          </motion.div>

          {/* Distributor Breakdown */}
          <motion.div
            initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.5 }}
            style={{
              background: "var(--bg-surface)", border: "1px solid var(--border-light)",
              borderRadius: "20px", padding: "24px"
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "24px" }}>
               <h3 style={{ fontSize: "18px", fontWeight: 700, color: "var(--text-color)", display: "flex", alignItems: "center", gap: "8px", margin: 0 }}>
                 <PieIcon size={20} color="var(--primary-500)"/> This Month — Purchases by Distributor
               </h3>
            </div>
            {distributorData.length > 0 ? (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "24px", alignItems: "center" }}>
                <ResponsiveContainer width="100%" height={260}>
                  <PieChart>
                    <Pie
                      data={distributorData} dataKey="total_spend" nameKey="distributor_name"
                      cx="50%" cy="50%" innerRadius={60} outerRadius={100} paddingAngle={2}
                      label={(d) => `${Math.round(d.percent * 100)}%`}
                    >
                      {distributorData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                    </Pie>
                    <Tooltip formatter={(v) => formatMoney(v)} contentStyle={{ borderRadius: "12px", border: "none", boxShadow: "var(--shadow-md)" }} />
                  </PieChart>
                </ResponsiveContainer>
                
                <table className="table" style={{ margin: 0 }}>
                  <thead><tr><th>Distributor</th><th>Spend</th><th>Bills</th></tr></thead>
                  <tbody>
                    {distributorData.map((d, i) => (
                      <tr key={d.distributor_id ?? d.distributor_name}>
                        <td style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                           <span style={{ width: "10px", height: "10px", borderRadius: "50%", background: PIE_COLORS[i % PIE_COLORS.length] }}></span>
                           {d.distributor_name}
                        </td>
                        <td style={{ fontWeight: 600 }}>{formatMoney(d.total_spend)}</td>
                        <td>{d.bill_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p style={{ color: "var(--text-muted)" }}>No confirmed bills this month yet.</p>
            )}
          </motion.div>
        </div>
        
        {/* Right Column Area */}
        <div style={{ display: "flex", flexDirection: "column", gap: "32px" }}>
          
          {/* Recent Price Changes */}
          <motion.div
            initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.5, delay: 0.3 }}
            style={{
              background: "var(--bg-surface)", border: "1px solid var(--border-light)",
              borderRadius: "20px", padding: "24px", display: "flex", flexDirection: "column"
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "24px" }}>
              <h3 style={{ fontSize: "18px", fontWeight: 700, color: "var(--text-color)", display: "flex", alignItems: "center", gap: "8px", margin: 0 }}>
                <TrendingUp size={20} color="var(--primary-500)" /> Biggest Price Movements
              </h3>
              <select 
                value={priceWindow} onChange={(e) => setPriceWindow(Number(e.target.value))} 
                style={{ padding: "6px 12px", borderRadius: "8px", border: "1px solid var(--border-light)", background: "var(--bg-app)", color: "var(--text-main)", fontWeight: 600 }}
              >
                <option value={30}>Last 30 days</option>
                <option value={90}>Last 90 days</option>
                <option value={365}>Last year</option>
              </select>
            </div>
            
            {priceChanges.length > 0 ? (
              <table className="table" style={{ margin: 0 }}>
                <thead><tr><th>Medicine</th><th>Old → New</th><th>Change</th></tr></thead>
                <tbody>
                  {priceChanges.map((p) => (
                    <tr key={p.medicine_id}>
                      <td style={{ fontWeight: 600 }}>{p.medicine_name}</td>
                      <td><span style={{ textDecoration: "line-through", color: "var(--text-muted)", marginRight: "6px" }}>₹{p.old_rate}</span> <b>₹{p.new_rate}</b></td>
                      <td>
                        <span style={{ 
                          padding: "4px 8px", borderRadius: "12px", fontSize: "12px", fontWeight: 700,
                          background: p.pct_change > 0 ? "var(--danger-bg)" : "var(--success-bg)",
                          color: p.pct_change > 0 ? "var(--danger-text)" : "var(--success-text)"
                        }}>
                          {p.pct_change >= 0 ? "▲" : "▼"} {Math.abs(p.pct_change)}%
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", opacity: 0.5, padding: "40px 0" }}>
                <Clock size={40} style={{ marginBottom: "16px", color: "var(--text-muted)" }} />
                <p style={{ fontSize: "14px", textAlign: "center", fontWeight: 500 }}>No rate changes recorded in this window yet.</p>
              </div>
            )}
          </motion.div>
        </div>
      </div>
      
      {/* Bottom Grid for Top Spend & Top Selling */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "32px" }}>
        
        {/* Top Spend */}
        <motion.div
            initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.6 }}
            style={{
              background: "var(--bg-surface)", border: "1px solid var(--border-light)",
              borderRadius: "20px", padding: "24px"
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "24px" }}>
              <h3 style={{ fontSize: "18px", fontWeight: 700, color: "var(--text-color)", display: "flex", alignItems: "center", gap: "8px", margin: 0 }}>
                <DollarSign size={20} color="var(--success-text)" /> Top Medicines by Spend (this month)
              </h3>
            </div>
            {topSpend.length > 0 ? (
              <div style={{ height: "300px", width: "100%" }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={topSpend} layout="vertical" margin={{ top: 0, right: 30, left: 40, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="var(--border-light)" />
                    <XAxis type="number" fontSize={11} tickFormatter={(v) => `₹${v / 1000}k`} stroke="var(--text-muted)" />
                    <YAxis type="category" dataKey="medicine_name" width={140} fontSize={12} stroke="var(--text-main)" fontWeight={600} />
                    <Tooltip formatter={(value) => formatMoney(value)} contentStyle={{ borderRadius: "12px", border: "none", boxShadow: "var(--shadow-md)" }} cursor={{ fill: "var(--bg-app)" }} />
                    <Bar dataKey="total_spend" fill="var(--success-text)" radius={[0, 6, 6, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p style={{ color: "var(--text-muted)" }}>No data available.</p>
            )}
        </motion.div>

        {/* Top Selling */}
        <motion.div
            initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.7 }}
            style={{
              background: "var(--bg-surface)", border: "1px solid var(--border-light)",
              borderRadius: "20px", padding: "24px"
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "24px" }}>
              <h3 style={{ fontSize: "18px", fontWeight: 700, color: "var(--text-color)", display: "flex", alignItems: "center", gap: "8px", margin: 0 }}>
                <Flame size={20} color="var(--accent-500)" /> Top Selling Medicines (30d)
              </h3>
            </div>
            {topSelling.length > 0 ? (
              <div style={{ height: "300px", width: "100%" }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={topSelling} layout="vertical" margin={{ top: 0, right: 30, left: 40, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="var(--border-light)" />
                    <XAxis type="number" fontSize={11} stroke="var(--text-muted)" />
                    <YAxis type="category" dataKey="medicine_name" width={140} fontSize={12} stroke="var(--text-main)" fontWeight={600} />
                    <Tooltip formatter={(value) => [`${value} units`, "Sold"]} contentStyle={{ borderRadius: "12px", border: "none", boxShadow: "var(--shadow-md)" }} cursor={{ fill: "var(--bg-app)" }} />
                    <Bar dataKey="qty_sold" fill="var(--accent-500)" radius={[0, 6, 6, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p style={{ color: "var(--text-muted)" }}>No sales recorded yet.</p>
            )}
        </motion.div>

      </div>
    </motion.div>
  );
}
