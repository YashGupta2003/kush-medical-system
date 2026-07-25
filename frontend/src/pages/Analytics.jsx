import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  PieChart, Pie, Cell, Legend,
} from "recharts";
import { api } from "../api/client.js";

const PIE_COLORS = ["#2563eb", "#16a34a", "#ea580c", "#9333ea", "#0891b2", "#db2777", "#65a30d", "#d97706"];

function StatCard({ label, value, sub, warn }) {
  return (
    <div className={`stat-box ${warn ? "warn" : ""}`}>
      <div className="value">{value}</div>
      <div className="label">{label}</div>
      {sub && <div style={{ fontSize: 11, color: "#999", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function formatMoney(n) {
  if (n == null) return "₹0";
  return "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

export default function Analytics() {
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

  return (
    <div>
      <div className="card">
        <h2 style={{ marginBottom: 4 }}>📊 Analytics Dashboard</h2>
        <p style={{ color: "#666", fontSize: 13, marginTop: 0 }}>
          Live business intelligence, pulled from your bills, stock, sales, and price history.
        </p>

        {overview && (
          <div className="stat-row">
            <StatCard
              label="This month's spend"
              value={formatMoney(overview.this_month_spend)}
              sub={
                overview.spend_change_pct == null ? "no data for last month"
                : `${overview.spend_change_pct >= 0 ? "▲" : "▼"} ${Math.abs(overview.spend_change_pct)}% vs last month`
              }
              warn={overview.spend_change_pct > 15}
            />
            <StatCard label="Stock value on hand" value={formatMoney(overview.stock_value)} />
            <StatCard label="Low stock items" value={overview.low_stock_count} warn={overview.low_stock_count > 0} />
            <StatCard label="Expiring soon / expired" value={overview.expiring_critical} warn={overview.expiring_critical > 0} />
            <StatCard label="Bills awaiting review" value={overview.pending_review_count} warn={overview.pending_review_count > 0} />
            <StatCard label="Avg. bill value (this month)" value={formatMoney(overview.avg_bill_value)} />
          </div>
        )}
      </div>

      {loading && <p>Loading analytics...</p>}

      {!loading && (
        <>
          <div className="card">
            <h3 style={{ marginTop: 0 }}>Monthly Purchase Spend (last 6 months)</h3>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={monthlySpend}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="label" fontSize={12} />
                <YAxis fontSize={12} tickFormatter={(v) => `₹${v / 1000}k`} />
                <Tooltip formatter={(v) => formatMoney(v)} />
                <Bar dataKey="total_spend" fill="#2563eb" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div className="card">
              <h3 style={{ marginTop: 0 }}>This Month — Purchases by Distributor</h3>
              {distributorData.length === 0 ? (
                <p style={{ color: "#888", fontSize: 13 }}>No confirmed bills this month yet.</p>
              ) : (
                <>
                  <ResponsiveContainer width="100%" height={220}>
                    <PieChart>
                      <Pie
                        data={distributorData} dataKey="total_spend" nameKey="distributor_name"
                        cx="50%" cy="50%" outerRadius={80} label={(d) => `${Math.round(d.percent * 100)}%`}
                      >
                        {distributorData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                      </Pie>
                      <Tooltip formatter={(v) => formatMoney(v)} />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                    </PieChart>
                  </ResponsiveContainer>
                  <table style={{ marginTop: 8 }}>
                    <thead><tr><th>Distributor</th><th>Spend</th><th>Bills</th></tr></thead>
                    <tbody>
                      {distributorData.map((d) => (
                        <tr key={d.distributor_id ?? d.distributor_name}>
                          <td>{d.distributor_name}</td><td>{formatMoney(d.total_spend)}</td><td>{d.bill_count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}
            </div>

            <div className="card">
              <h3 style={{ marginTop: 0 }}>Top Medicines by Spend (this month)</h3>
              {topSpend.length === 0 ? (
                <p style={{ color: "#888", fontSize: 13 }}>No confirmed bills this month yet.</p>
              ) : (
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={topSpend} layout="vertical" margin={{ left: 40 }}>
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                    <XAxis type="number" fontSize={11} tickFormatter={(v) => `₹${v / 1000}k`} />
                    <YAxis type="category" dataKey="medicine_name" width={140} fontSize={11} />
                    <Tooltip formatter={(v) => formatMoney(v)} />
                    <Bar dataKey="total_spend" fill="#16a34a" radius={[0, 6, 6, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div className="card">
              <div className="flex-between">
                <h3 style={{ margin: 0 }}>💹 Biggest Price Movements</h3>
                <select value={priceWindow} onChange={(e) => setPriceWindow(Number(e.target.value))}>
                  <option value={30}>Last 30 days</option>
                  <option value={90}>Last 90 days</option>
                  <option value={365}>Last year</option>
                </select>
              </div>
              {priceChanges.length === 0 ? (
                <p style={{ color: "#888", fontSize: 13 }}>No rate changes recorded in this window yet.</p>
              ) : (
                <table style={{ marginTop: 8 }}>
                  <thead><tr><th>Medicine</th><th>Old → New</th><th>Change</th></tr></thead>
                  <tbody>
                    {priceChanges.map((p) => (
                      <tr key={p.medicine_id}>
                        <td>{p.medicine_name}</td>
                        <td>₹{p.old_rate} → ₹{p.new_rate}</td>
                        <td>
                          <span className={`badge ${p.pct_change >= 0 ? "unmatched" : "auto"}`}>
                            {p.pct_change >= 0 ? "▲" : "▼"} {Math.abs(p.pct_change)}%
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            <div className="card">
              <h3 style={{ marginTop: 0 }}>🔥 Top Sellers (last 30 days)</h3>
              {topSelling.length === 0 ? (
                <p style={{ color: "#888", fontSize: 13 }}>No sales recorded yet — try the "Record a Sale" screen.</p>
              ) : (
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={topSelling} layout="vertical" margin={{ left: 40 }}>
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                    <XAxis type="number" fontSize={11} />
                    <YAxis type="category" dataKey="medicine_name" width={140} fontSize={11} />
                    <Tooltip />
                    <Bar dataKey="qty_sold" fill="#9333ea" radius={[0, 6, 6, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}