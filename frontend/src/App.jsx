import { useEffect, useState } from "react";
import { Routes, Route, NavLink, useLocation } from "react-router-dom";
import UploadBill from "./pages/UploadBill.jsx";
import ReviewBill from "./pages/ReviewBill.jsx";
import SearchDashboard from "./pages/SearchDashboard.jsx";
import Substitutes from "./pages/Substitutes.jsx";
import GraphExplorer from "./pages/GraphExplorer.jsx";
import BillHistory from "./pages/BillHistory.jsx";
import Stock from "./pages/Stock.jsx";
import Expiry from "./pages/Expiry.jsx";
import Analytics from "./pages/Analytics.jsx";
import GstReport from "./pages/GstReport.jsx";
import BarcodeScan from "./pages/BarcodeScan.jsx";
import Users from "./pages/Users.jsx";
import Login from "./pages/Login.jsx";
import { useAuth } from "./auth/AuthContext.jsx";
import { RequireAuth, RequireOwner } from "./auth/guards.jsx";
import { api } from "./api/client.js";
import Copilot from "./pages/Copilot.jsx";
import PointOfSale from "./pages/PointOfSale.jsx";
import AuditTrail from "./pages/AuditTrail.jsx";
import Customers from "./pages/Customers.jsx";
import Network from "./pages/Network.jsx";
import Predictive from "./pages/Predictive.jsx";
import ColdChain from "./pages/ColdChain.jsx";
import Surveillance from "./pages/Surveillance.jsx";
import TrustScore from "./pages/TrustScore.jsx";

import { NotificationBell } from "./pages/NotificationCenter.jsx";


const NAV_ITEMS = [
  { to: "/analytics", label: "Analytics", icon: "📊", ownerOnly: true },
  { to: "/", label: "Search & Master", icon: "🔍", end: true },
  { to: "/substitutes", label: "Substitutes", icon: "🔄" },
  { to: "/graph", label: "PharmaGraph", icon: "🕸️" },
  { to: "/scan", label: "Barcode Scan", icon: "📷" },
  { to: "/upload", label: "Upload Bill", icon: "📤" },
  { to: "/bills", label: "Review Queue", icon: "🗂️" },
  { to: "/stock", label: "Stock & Reorder", icon: "📦" },
  { to: "/expiry", label: "Expiry Tracker", icon: "⏳", badgeKey: "urgent" },
  { to: "/gst", label: "GST Summary", icon: "🧾", ownerOnly: true },
  { to: "/users", label: "Staff", icon: "👥", ownerOnly: true },
  { to: "/copilot", label: "PharmaCopilot", icon: "🤖", ownerOnly: true },
  { to: "/pos", label: "Point of Sale", icon: "🛒" },
  { to: "/customers", label: "Customers", icon: "👤" },
  { to: "/network", label: "Pharma Network", icon: "🌐" },
  { to: "/cold-chain", label: "Cold Chain", icon: "🧊" },

  { to: "/predictive", label: "Predictive Intel", icon: "🔮", ownerOnly: true },
  { to: "/surveillance", label: "Health Surveillance", icon: "📈", ownerOnly: true },
  { to: "/trust-score", label: "Supply Trust", icon: "🛡️", ownerOnly: true },
  { to: "/audit", label: "TrustChain", icon: "🔗", ownerOnly: true },
];

function HealthBadge() {
  const [health, setHealth] = useState(null);

  useEffect(() => {
    function check() {
      api.getHealth()
        .then(setHealth)
        .catch(() => setHealth({ status: "down" }));
    }
    check();
    const interval = setInterval(check, 15000);
    return () => clearInterval(interval);
  }, []);

  if (!health) return null;

  const isHealthy = health.status === "healthy";
  const statusColor = isHealthy ? "#10b981" : health.status === "degraded" ? "#f59e0b" : "#ef4444";

  return (
    <div
      title={`System Status: ${health.status.toUpperCase()}\nDB: ${health.services?.database?.status || 'N/A'}\nRedis: ${health.services?.redis?.status || 'N/A'}\nCelery Workers: ${health.services?.celery?.active_workers ?? 'N/A'}`}
      className="health-badge-glass"
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        borderRadius: 20,
        fontSize: 12,
        color: "#e2e8f0",
        cursor: "help",
      }}
    >
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: statusColor,
          boxShadow: `0 0 6px ${statusColor}`,
        }}
      />
      <span>System {health.status}</span>
    </div>
  );
}

function NavBar() {
  const { user, logout, isOwner } = useAuth();
  const [urgentCount, setUrgentCount] = useState(0);

  useEffect(() => {
    if (!user) return;
    function poll() {
      api.getExpirySummary()
        .then((s) => setUrgentCount((s.expired || 0) + (s.critical || 0)))
        .catch(() => {});
    }
    poll();
    const interval = setInterval(poll, 15000);
    return () => clearInterval(interval);
  }, [user]);

  if (!user) return null;

  return (
    <nav className="app-nav">
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <div className="app-nav-brand">
          <span className="app-nav-brand-icon">💊</span>
          Kush Medical Hall
        </div>
        <HealthBadge />
      </div>
      
      <div className="app-nav-links">
        {NAV_ITEMS.filter((item) => !item.ownerOnly || isOwner).map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
          >
            <span className="nav-icon">{item.icon}</span>
            <span className="nav-text">{item.label}</span>
            {item.badgeKey === "urgent" && urgentCount > 0 && (
              <span className="nav-badge">{urgentCount}</span>
            )}
          </NavLink>
        ))}
      </div>
      
      <div className="user-profile-section">
        <div className="user-profile-info">
          <div style={{ width: 28, height: 28, borderRadius: '50%', background: 'linear-gradient(135deg, #2563eb, #38bdf8)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontWeight: 'bold', fontSize: 13, boxShadow: '0 2px 6px rgba(37, 99, 235, 0.25)' }}>
            {(user.full_name || user.username).charAt(0).toUpperCase()}
          </div>
          <span className="user-profile-name">{user.full_name || user.username}</span>
          <span className="badge" style={{ marginLeft: 6, background: '#ecfdf5', color: '#059669', border: '1px solid #a7f3d0', padding: '2px 8px', fontSize: 11 }}>{user.role}</span>
        </div>
        <NotificationBell />
        <button className="user-profile-logout" onClick={logout}>Logout</button>
      </div>
    </nav>
  );
}

export default function App() {
  const { loading ,isOwner } = useAuth();
  const location = useLocation();
  const isLoginPage = location.pathname === "/login";

  if (loading) return <p style={{ padding: 20 }}>Loading System...</p>;

  return (
    <div>
      {!isLoginPage && <NavBar />}
      <div className={isLoginPage ? "" : "container"}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<RequireAuth><SearchDashboard /></RequireAuth>} />
          <Route path="/substitutes" element={<RequireAuth><Substitutes /></RequireAuth>} />
          <Route path="/graph" element={<RequireAuth><GraphExplorer isOwner={isOwner} /></RequireAuth>} />
          <Route path="/scan" element={<RequireAuth><BarcodeScan /></RequireAuth>} />
          <Route path="/upload" element={<RequireAuth><UploadBill /></RequireAuth>} />
          <Route path="/bills" element={<RequireAuth><BillHistory /></RequireAuth>} />
          <Route path="/review/:billId" element={<RequireAuth><ReviewBill /></RequireAuth>} />
          <Route path="/stock" element={<RequireAuth><Stock /></RequireAuth>} />
          <Route path="/expiry" element={<RequireAuth><Expiry /></RequireAuth>} />
          <Route path="/analytics" element={<RequireOwner><Analytics /></RequireOwner>} />
          <Route path="/gst" element={<RequireOwner><GstReport /></RequireOwner>} />
          <Route path="/users" element={<RequireOwner><Users /></RequireOwner>} />
          <Route path="/copilot" element={<RequireOwner><Copilot /></RequireOwner>} />
          <Route path="/pos" element={<RequireAuth><PointOfSale /></RequireAuth>} />
          <Route path="/customers" element={<RequireAuth><Customers /></RequireAuth>} />
          <Route path="/network" element={<RequireAuth><Network isOwner={isOwner} /></RequireAuth>} />
           <Route path="/predictive" element={<RequireOwner><Predictive /></RequireOwner>} />
          <Route path="/audit" element={<RequireOwner><AuditTrail /></RequireOwner>} />
          <Route path="/cold-chain" element={<RequireAuth><ColdChain isOwner={isOwner} /></RequireAuth>} />
          <Route path="/surveillance" element={<RequireOwner><Surveillance /></RequireOwner>} />
          <Route path="/trust-score" element={<RequireOwner><TrustScore /></RequireOwner>} />

          <Route path="/notifications" element={<RequireAuth><div /></RequireAuth>} />
        </Routes>
      </div>
    </div>
  );
}