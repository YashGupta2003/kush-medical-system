import { useEffect, useState } from "react";
import { Routes, Route, NavLink, useLocation } from "react-router-dom";
import UploadBill from "./pages/UploadBill.jsx";
import ReviewBill from "./pages/ReviewBill.jsx";
import SearchDashboard from "./pages/SearchDashboard.jsx";
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

const NAV_ITEMS = [
  { to: "/analytics", label: "Analytics", icon: "📊", ownerOnly: true },
  { to: "/", label: "Search", icon: "🔍", end: true },
  { to: "/scan", label: "Scan", icon: "📷" },
  { to: "/upload", label: "Upload bill", icon: "📤" },
  { to: "/bills", label: "Review queue", icon: "🗂️" },
  { to: "/stock", label: "Stock & Reorder", icon: "📦" },
  { to: "/expiry", label: "Expiry Tracker", icon: "⏳", badgeKey: "urgent" },
  { to: "/gst", label: "GST Report", icon: "🧾", ownerOnly: true },
  { to: "/users", label: "Staff", icon: "👥", ownerOnly: true },
];

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
      <div className="app-nav-brand">💊 Kush Medical Hall</div>
      <div className="app-nav-links">
        {NAV_ITEMS.filter((item) => !item.ownerOnly || isOwner).map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
          >
            <span className="nav-icon">{item.icon}</span>
            <span>{item.label}</span>
            {item.badgeKey === "urgent" && urgentCount > 0 && (
              <span className="nav-badge">{urgentCount}</span>
            )}
          </NavLink>
        ))}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, color: "#cfcfd6", fontSize: 13 }}>
        <span>{user.full_name || user.username} <span className="badge auto" style={{ marginLeft: 4 }}>{user.role}</span></span>
        <button className="secondary" onClick={logout}>Logout</button>
      </div>
    </nav>
  );
}

export default function App() {
  const { loading } = useAuth();
  const location = useLocation();
  const isLoginPage = location.pathname === "/login";

  if (loading) return <p style={{ padding: 20 }}>Loading...</p>;

  return (
    <div>
      {!isLoginPage && <NavBar />}
      <div className={isLoginPage ? "" : "container"}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<RequireAuth><SearchDashboard /></RequireAuth>} />
          <Route path="/scan" element={<RequireAuth><BarcodeScan /></RequireAuth>} />
          <Route path="/upload" element={<RequireAuth><UploadBill /></RequireAuth>} />
          <Route path="/bills" element={<RequireAuth><BillHistory /></RequireAuth>} />
          <Route path="/review/:billId" element={<RequireAuth><ReviewBill /></RequireAuth>} />
          <Route path="/stock" element={<RequireAuth><Stock /></RequireAuth>} />
          <Route path="/expiry" element={<RequireAuth><Expiry /></RequireAuth>} />
          <Route path="/analytics" element={<RequireOwner><Analytics /></RequireOwner>} />
          <Route path="/gst" element={<RequireOwner><GstReport /></RequireOwner>} />
          <Route path="/users" element={<RequireOwner><Users /></RequireOwner>} />
        </Routes>
      </div>
    </div>
  );
}