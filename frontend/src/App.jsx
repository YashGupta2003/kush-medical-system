import { useEffect, useState } from "react";
import { Routes, Route, NavLink } from "react-router-dom";
import UploadBill from "./pages/UploadBill.jsx";
import ReviewBill from "./pages/ReviewBill.jsx";
import SearchDashboard from "./pages/SearchDashboard.jsx";
import BillHistory from "./pages/BillHistory.jsx";
import Stock from "./pages/Stock.jsx";
import Expiry from "./pages/Expiry.jsx";
import { api } from "./api/client.js";

const NAV_ITEMS = [
  { to: "/", label: "Search", icon: "🔍", end: true },
  { to: "/upload", label: "Upload bill", icon: "📤" },
  { to: "/bills", label: "Review queue", icon: "🗂️" },
  { to: "/stock", label: "Stock & Reorder", icon: "📦" },
  { to: "/expiry", label: "Expiry Tracker", icon: "⏳", badgeKey: "urgent" },
];

export default function App() {
  const [urgentCount, setUrgentCount] = useState(0);

  useEffect(() => {
    function poll() {
      api.getExpirySummary()
        .then((s) => setUrgentCount((s.expired || 0) + (s.critical || 0)))
        .catch(() => {});
    }
    poll();
    const interval = setInterval(poll, 15000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div>
      <nav className="app-nav">
        <div className="app-nav-brand">💊 Kush Medical Hall</div>
        <div className="app-nav-links">
          {NAV_ITEMS.map((item) => (
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
      </nav>
      <div className="container">
        <Routes>
          <Route path="/" element={<SearchDashboard />} />
          <Route path="/upload" element={<UploadBill />} />
          <Route path="/bills" element={<BillHistory />} />
          <Route path="/review/:billId" element={<ReviewBill />} />
          <Route path="/stock" element={<Stock />} />
          <Route path="/expiry" element={<Expiry />} />
        </Routes>
      </div>
    </div>
  );
}