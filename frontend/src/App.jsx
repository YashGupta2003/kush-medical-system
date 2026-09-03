import { useEffect, useState, useRef } from "react";
import { Routes, Route, NavLink, useLocation, Navigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { 
  BarChart2, Search, RefreshCw, Network as NetworkIcon, Scan, Upload, FileStack, Package, 
  Hourglass, FileText, Users as UsersIcon, Bot, ShoppingCart, UserCircle, Globe, Snowflake, 
  Lightbulb, TrendingUp, ShieldCheck, Link2, Hexagon, Box, Activity, Shield, ChevronDown
} from 'lucide-react';

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
import Landing from "./pages/Landing.jsx";
import Register from "./pages/Register.jsx";
import SetupWizard from "./pages/SetupWizard.jsx";
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
import SmartPurchase from "./pages/SmartPurchase.jsx";
import ProfitOptimizer from "./pages/ProfitOptimizer.jsx";
import MedicalBackground from "./components/MedicalBackground.jsx";
import CommandPalette from "./components/CommandPalette.jsx";
import ThemeToggle from "./components/ThemeToggle.jsx";

import { NotificationBell } from "./pages/NotificationCenter.jsx";
import NotificationCenter from "./pages/NotificationCenter.jsx";
import Prescriptions from "./pages/Prescriptions.jsx";


const NAV_GROUPS = [
  {
    label: "Intelligence",
    icon: <Activity size={16} />,
    items: [
      { to: "/analytics", label: "Analytics", icon: <BarChart2 size={16} />, ownerOnly: true },
      { to: "/", label: "Central Command", icon: <Search size={16} />, end: true },
      { to: "/copilot", label: "PharmaCopilot", icon: <Bot size={16} />, ownerOnly: true },
      { to: "/predictive", label: "Predictive Intel", icon: <Lightbulb size={16} />, ownerOnly: true },
      { to: "/surveillance", label: "Health Surveillance", icon: <TrendingUp size={16} />, ownerOnly: true },
      { to: "/graph", label: "PharmaGraph", icon: <NetworkIcon size={16} /> },
      { to: "/smart-purchase", label: "Smart Purchase AI", icon: <ShoppingCart size={16} />, ownerOnly: true },
    ]
  },
  {
    label: "Operations",
    icon: <Box size={16} />,
    items: [
      { to: "/pos", label: "Point of Sale", icon: <ShoppingCart size={16} /> },
      { to: "/prescriptions", label: "Prescriptions", icon: <FileText size={16} /> },
      { to: "/scan", label: "Barcode Scan", icon: <Scan size={16} /> },
      { to: "/substitutes", label: "Substitutes", icon: <RefreshCw size={16} /> },
      { to: "/customers", label: "Customers", icon: <UserCircle size={16} /> },
      { to: "/network", label: "Pharma Network", icon: <Globe size={16} /> },
    ]
  },
  {
    label: "Inventory",
    icon: <Package size={16} />,
    items: [
      { to: "/stock", label: "Stock & Reorder", icon: <Package size={16} /> },
      { to: "/expiry", label: "Expiry Tracker", icon: <Hourglass size={16} />, badgeKey: "urgent" },
      { to: "/cold-chain", label: "Cold Chain", icon: <Snowflake size={16} /> },
    ]
  },
  {
    label: "Finance",
    icon: <FileText size={16} />,
    items: [
      { to: "/upload", label: "Upload Bill", icon: <Upload size={16} /> },
      { to: "/bills", label: "Review Queue", icon: <FileStack size={16} /> },
      { to: "/gst", label: "GST Summary", icon: <FileText size={16} />, ownerOnly: true },
      { to: "/profit", label: "Profit Optimizer", icon: <TrendingUp size={16} />, ownerOnly: true },
    ]
  },
  {
    label: "System",
    icon: <Shield size={16} />,
    items: [
      { to: "/users", label: "Staff", icon: <UsersIcon size={16} />, ownerOnly: true },
      { to: "/trust-score", label: "Supply Trust", icon: <ShieldCheck size={16} />, ownerOnly: true },
      { to: "/audit", label: "TrustChain", icon: <Link2 size={16} />, ownerOnly: true },
    ]
  }
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
  const statusColor = isHealthy ? "var(--success-text)" : health.status === "degraded" ? "var(--warning-text)" : "var(--danger-text)";
  const bgBadge = isHealthy ? "var(--success-bg)" : health.status === "degraded" ? "var(--warning-bg)" : "var(--danger-bg)";

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      title={`System Status: ${health.status.toUpperCase()}\nDB: ${health.services?.database?.status || 'N/A'}\nRedis: ${health.services?.redis?.status || 'N/A'}\nCelery Workers: ${health.services?.celery?.active_workers ?? 'N/A'}`}
      className="badge"
      style={{ display: "flex", alignItems: "center", gap: 6, padding: "4px 10px", cursor: "help", background: bgBadge, color: statusColor, border: `1px solid ${statusColor}40` }}
    >
      <span style={{ width: 6, height: 6, borderRadius: "50%", background: statusColor, boxShadow: `0 0 6px ${statusColor}` }} />
      <span>System {health.status}</span>
    </motion.div>
  );
}

function NavDropdownGroup({ group, isOwner, urgentCount }) {
  const [isOpen, setIsOpen] = useState(false);
  const location = useLocation();

  const filteredItems = group.items.filter(item => !item.ownerOnly || isOwner);
  if (filteredItems.length === 0) return null;

  const isActiveGroup = filteredItems.some(item => 
    item.end ? location.pathname === item.to : location.pathname.startsWith(item.to)
  );

  const groupHasUrgent = filteredItems.some(item => item.badgeKey === "urgent" && urgentCount > 0);

  return (
    <div 
      style={{ position: "relative" }}
      onMouseEnter={() => setIsOpen(true)}
      onMouseLeave={() => setIsOpen(false)}
    >
      <motion.div
        whileHover={{ scale: 1.08 }}
        whileTap={{ scale: 0.95 }}
        transition={{ type: "spring", stiffness: 400, damping: 17 }}
        style={{
          display: "flex", alignItems: "center", gap: 6,
          padding: "8px 14px",
          borderRadius: "var(--radius-full)",
          background: isActiveGroup ? "var(--primary-50)" : (isOpen ? "rgba(0,0,0,0.06)" : "transparent"),
          color: isActiveGroup ? "var(--primary-600)" : "var(--text-color)",
          fontWeight: 600,
          fontSize: "var(--text-sm)",
          cursor: "pointer",
          transition: "background 0.3s ease, color 0.3s ease",
        }}
      >
        {group.icon}
        <motion.span transition={{ duration: 0.2 }} style={{ display: "inline-block" }}>
          {group.label}
        </motion.span>
        <ChevronDown size={14} style={{ opacity: 0.6, transform: isOpen ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 0.2s" }} />
        {groupHasUrgent && <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--danger-text)", marginLeft: 4 }} />}
      </motion.div>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.95, transition: { duration: 0.1 } }}
            transition={{ type: "spring", stiffness: 400, damping: 25 }}
            style={{
              position: "absolute", top: "100%", left: "50%", transform: "translateX(-50%)",
              marginTop: 8, minWidth: 220,
              background: "var(--bg-surface)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-lg)",
              boxShadow: "0 10px 40px rgba(0,0,0,0.08)",
              padding: 8,
              zIndex: 9999,
              display: "flex", flexDirection: "column", gap: 4
            }}
          >
            {filteredItems.map(item => (
              <NavLink key={item.to} to={item.to} end={item.end} style={{ textDecoration: "none" }} onClick={() => setIsOpen(false)}>
                {({ isActive }) => (
                  <motion.div
                    whileHover={{ scale: 1.02, x: 4, background: "var(--bg-surface-hover)" }}
                    style={{
                      display: "flex", alignItems: "center", gap: 10,
                      padding: "10px 12px",
                      borderRadius: "var(--radius-md)",
                      color: isActive ? "var(--primary-600)" : "var(--text-main)",
                      background: isActive ? "var(--primary-50)" : "transparent",
                      fontWeight: isActive ? 600 : 500,
                      fontSize: "var(--text-sm)",
                    }}
                  >
                    {item.icon}
                    <span style={{ flex: 1 }}>{item.label}</span>
                    {item.badgeKey === "urgent" && urgentCount > 0 && (
                      <span className="badge" style={{ background: "var(--danger-text)", color: "#fff", padding: "2px 6px", fontSize: "10px" }}>{urgentCount}</span>
                    )}
                  </motion.div>
                )}
              </NavLink>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
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
    <nav className="app-nav" style={{ 
      padding: "16px 32px", 
      borderBottom: "1px solid var(--border-subtle)", 
      background: "rgba(255, 255, 255, 0.7)",
      backdropFilter: "blur(20px)",
      WebkitBackdropFilter: "blur(20px)",
      position: "sticky", top: 0, zIndex: 1000,
      display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, color: "var(--primary-600)", fontWeight: 800, fontSize: "1.2rem", letterSpacing: "-0.02em" }}>
          <div style={{ position: "relative", display: "flex", alignItems: "center", justifyContent: "center", background: "linear-gradient(135deg, var(--primary-500), var(--primary-700))", color: "#fff", width: 40, height: 40, borderRadius: 12, boxShadow: "0 4px 10px rgba(20, 184, 166, 0.3)" }}>
             <Hexagon size={24} strokeWidth={2.5} />
          </div>
          <span style={{ background: "linear-gradient(to right, var(--primary-600), var(--primary-800))", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            {user?.shop_name || "PharmOS"}
          </span>
        </div>

        <HealthBadge />
      </div>
      
      <div className="app-nav-links" style={{ display: "flex", gap: "8px", alignItems: "center", flex: 1, justifyContent: "center" }}>
        {NAV_GROUPS.map((group) => (
          <NavDropdownGroup key={group.label} group={group} isOwner={isOwner} urgentCount={urgentCount} />
        ))}
      </div>
      
      <div className="user-profile-section" style={{ display: "flex", alignItems: "center", gap: 20 }}>
        <ThemeToggle />
        <NotificationBell />
        <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "6px 16px", background: "var(--bg-surface)", borderRadius: "var(--radius-full)", border: "1px solid var(--border-subtle)", boxShadow: "0 2px 10px rgba(0,0,0,0.03)" }}>
          <div style={{ width: 30, height: 30, borderRadius: '50%', background: 'linear-gradient(135deg, var(--primary-500), var(--primary-600))', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontWeight: 700, fontSize: 14 }}>
            {(user.full_name || user.username).charAt(0).toUpperCase()}
          </div>
          <div style={{ display: "flex", flexDirection: "column", lineHeight: 1.1 }}>
            <span style={{ fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--text-main)" }}>{user.full_name || user.username}</span>
            <span style={{ fontSize: "10px", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: 700 }}>{user.role}</span>
          </div>
        </div>
        <motion.button 
          onClick={logout}
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          style={{ 
            background: "transparent", border: "1px solid var(--border-strong)", 
            padding: "8px 16px", borderRadius: "var(--radius-full)", 
            color: "var(--text-main)", fontWeight: 600, fontSize: "var(--text-sm)", 
            cursor: "pointer", transition: "all 0.2s" 
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-surface-hover)"; e.currentTarget.style.borderColor = "var(--text-main)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.borderColor = "var(--border-strong)"; }}
        >
          Logout
        </motion.button>
      </div>
    </nav>
  );
}

const PageWrapper = ({ children }) => (
  <motion.div
    initial={{ opacity: 0, y: 15 }}
    animate={{ opacity: 1, y: 0 }}
    exit={{ opacity: 0, y: -15 }}
    transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
  >
    {children}
  </motion.div>
);

export default function App() {
  const { user, loading, isOwner } = useAuth();
  const location = useLocation();

  // Public pages that should NOT show the sidebar/navbar
  const isPublicPage = ["/login", "/register", "/setup"].includes(location.pathname)
    || (location.pathname === "/" && !user);

  if (loading) return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", background: "var(--bg-app)" }}>
      <div className="skeleton" style={{ width: 200, height: 40, borderRadius: 20 }}></div>
    </div>
  );

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", position: "relative" }}>
      <MedicalBackground />
      {!isPublicPage && <CommandPalette />}
      {!isPublicPage && <NavBar />}
      <div className={isPublicPage ? "" : "container"} style={{ flex: 1 }}>
        <AnimatePresence mode="wait">
          <Routes location={location} key={location.pathname}>
            {/* ── Public routes (no auth required) ── */}
            <Route path="/register" element={<Register />} />
            <Route path="/setup" element={<PageWrapper><SetupWizard /></PageWrapper>} />
            <Route path="/login" element={<PageWrapper><Login /></PageWrapper>} />

            {/* ── Landing: show marketing page if not logged in, dashboard if logged in ── */}
            <Route path="/" element={
              user
                ? <RequireAuth><PageWrapper><SearchDashboard /></PageWrapper></RequireAuth>
                : <Landing />
            } />

            {/* ── Protected routes ── */}
            <Route path="/substitutes" element={<RequireAuth><PageWrapper><Substitutes /></PageWrapper></RequireAuth>} />
            <Route path="/graph" element={<RequireAuth><PageWrapper><GraphExplorer isOwner={isOwner} /></PageWrapper></RequireAuth>} />
            <Route path="/scan" element={<RequireAuth><PageWrapper><BarcodeScan /></PageWrapper></RequireAuth>} />
            <Route path="/upload" element={<RequireAuth><PageWrapper><UploadBill /></PageWrapper></RequireAuth>} />
            <Route path="/bills" element={<RequireAuth><PageWrapper><BillHistory /></PageWrapper></RequireAuth>} />
            <Route path="/review/:billId" element={<RequireAuth><PageWrapper><ReviewBill /></PageWrapper></RequireAuth>} />
            <Route path="/stock" element={<RequireAuth><PageWrapper><Stock /></PageWrapper></RequireAuth>} />
            <Route path="/expiry" element={<RequireAuth><PageWrapper><Expiry /></PageWrapper></RequireAuth>} />
            <Route path="/analytics" element={<RequireOwner><PageWrapper><Analytics /></PageWrapper></RequireOwner>} />
            <Route path="/gst" element={<RequireOwner><PageWrapper><GstReport /></PageWrapper></RequireOwner>} />
            <Route path="/users" element={<RequireOwner><PageWrapper><Users /></PageWrapper></RequireOwner>} />
            <Route path="/copilot" element={<RequireOwner><PageWrapper><Copilot /></PageWrapper></RequireOwner>} />
            <Route path="/pos" element={<RequireAuth><PageWrapper><PointOfSale /></PageWrapper></RequireAuth>} />
            <Route path="/prescriptions" element={<RequireAuth><PageWrapper><Prescriptions /></PageWrapper></RequireAuth>} />
            <Route path="/customers" element={<RequireAuth><PageWrapper><Customers /></PageWrapper></RequireAuth>} />
            <Route path="/network" element={<RequireAuth><PageWrapper><Network isOwner={isOwner} /></PageWrapper></RequireAuth>} />
            <Route path="/predictive" element={<RequireOwner><PageWrapper><Predictive /></PageWrapper></RequireOwner>} />
            <Route path="/audit" element={<RequireOwner><PageWrapper><AuditTrail /></PageWrapper></RequireOwner>} />
            <Route path="/cold-chain" element={<RequireAuth><PageWrapper><ColdChain isOwner={isOwner} /></PageWrapper></RequireAuth>} />
            <Route path="/surveillance" element={<RequireOwner><PageWrapper><Surveillance /></PageWrapper></RequireOwner>} />
            <Route path="/trust-score" element={<RequireOwner><PageWrapper><TrustScore /></PageWrapper></RequireOwner>} />
            <Route path="/notifications" element={<RequireAuth><PageWrapper><NotificationCenter /></PageWrapper></RequireAuth>} />
            <Route path="/smart-purchase" element={<RequireOwner><PageWrapper><SmartPurchase /></PageWrapper></RequireOwner>} />
            <Route path="/profit" element={<RequireOwner><PageWrapper><ProfitOptimizer /></PageWrapper></RequireOwner>} />
            <Route path="*" element={<Navigate to="/" replace />} />

          </Routes>
        </AnimatePresence>
      </div>
    </div>
  );
}

