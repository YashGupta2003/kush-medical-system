import { useState } from "react";
import { useNavigate, useLocation, Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext.jsx";
import { useLandingTheme } from "../utils/theme.js";
import { motion } from "framer-motion";
import {
  Hexagon,
  Lock,
  AlertCircle,
  Mail,
  Eye,
  EyeOff,
  ArrowLeft,
  ArrowRight,
  ShieldCheck,
  ShieldAlert,
  Link2,
  Sun,
  Moon,
} from "lucide-react";
import { api } from "../api/client.js";
import "../styles/landing.css";

const HIGHLIGHTS = [
  {
    icon: ShieldCheck,
    title: "Multi-Tenant Session Isolation",
    desc: "Every database query and mutation is automatically scoped to your shop tenant, with owner-only wholesale rate protection.",
    tone: "emerald",
  },
  {
    icon: ShieldAlert,
    title: "Real-Time Clinical Safety Guardrail",
    desc: "Automated salt-overlap and drug interaction checks verify every billing cart against PharmaGraph before checkout.",
    tone: "sky",
  },
  {
    icon: Link2,
    title: "Tamper-Evident TrustChain Ledger",
    desc: "All confirmed purchase bills, cold-chain readings, and rate updates are hash-chained for audit-ready compliance.",
    tone: "violet",
  },
];

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { theme, toggleTheme } = useLandingTheme();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [shopName, setShopName] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    const normalizedEmail = email.trim();
    if (!normalizedEmail) {
      setError("Please enter your registered email or username.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const shopInfo = await api.lookupShop(normalizedEmail);
      setShopName(shopInfo.shop_name);
      await login(normalizedEmail, password, shopInfo.tenant_id);
      const redirectTo = location.state?.from || "/";
      navigate(redirectTo, { replace: true });
    } catch (err) {
      if (err.status === 404) {
        setError(`No shop account found for "${normalizedEmail}". Check your email or register a new shop below.`);
      } else {
        setError(err.message || "Failed to login. Please check your credentials.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="landing-root auth-page-shell" data-landing-theme={theme}>
      <div className="landing-grid-bg" />
      <div className="landing-glow-left" />
      <div className="landing-glow-right" />

      {/* Top Navigation */}
      <header className="auth-topbar">
        <Link to="/" style={{ display: "flex", alignItems: "center", gap: 10, textDecoration: "none", color: "var(--l-text-primary)" }}>
          <div style={{
            background: "var(--l-btn-primary-bg)",
            width: 34,
            height: 34,
            borderRadius: 10,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: "0 4px 12px rgba(16, 185, 129, 0.25)",
          }}>
            <Hexagon size={18} strokeWidth={2.5} color="#ffffff" />
          </div>
          <span style={{ fontFamily: "var(--font-display)", fontWeight: 800, fontSize: "1.12rem", color: "var(--l-text-primary)" }}>
            PharmOS
          </span>
        </Link>

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <button
            type="button"
            onClick={toggleTheme}
            className="landing-theme-btn"
            aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          >
            {theme === "dark" ? <Sun size={15} color="#fbbf24" /> : <Moon size={15} color="#0284c7" />}
            <span>{theme === "dark" ? "Light" : "Dark"}</span>
          </button>
          <Link to="/" className="landing-btn-secondary" style={{ padding: "8px 14px", fontSize: "0.84rem" }}>
            <ArrowLeft size={15} /> Back to Home
          </Link>
        </div>
      </header>

      {/* Full-Width 50/50 Split Auth Main */}
      <main className="auth-split-main">
        {/* Left Highlight Showcase */}
        <section className="auth-brand-pane">
          <div>
            <span className="mono-tag" style={{ color: "var(--l-emerald-text)", fontWeight: 700, display: "inline-flex", alignItems: "center", gap: 8, padding: "5px 12px", borderRadius: 9999, background: "var(--l-emerald-soft)", border: "1px solid var(--l-emerald-border)", marginBottom: 22 }}>
              <span className="live-dot" />
              SECURE TENANT WORKSPACE ACCESS
            </span>

            <h1 style={{ fontFamily: "var(--font-display)", fontSize: "clamp(1.9rem, 3.2vw, 2.85rem)", fontWeight: 800, lineHeight: 1.12, letterSpacing: "-0.03em", margin: "0 0 14px" }}>
              Welcome back to{" "}
              <span style={{
                background: "var(--l-headline-gradient)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}>
                PharmOS Command.
              </span>
            </h1>

            <p style={{ color: "var(--l-text-secondary)", fontSize: "1rem", lineHeight: 1.6, margin: "0 0 30px", maxWidth: 520 }}>
              Enter your registered email or staff username — PharmOS automatically resolves your shop tenant and loads role-scoped controls.
            </p>

            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {HIGHLIGHTS.map((h) => {
                const Icon = h.icon;
                return (
                  <div
                    key={h.title}
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      gap: 14,
                      padding: 16,
                      borderRadius: 16,
                      background: "var(--l-card-bg)",
                      border: "1px solid var(--l-border)",
                      boxShadow: "var(--l-shadow-card)",
                    }}
                  >
                    <div style={{
                      width: 38,
                      height: 38,
                      borderRadius: 10,
                      flexShrink: 0,
                      background: `var(--l-${h.tone}-soft)`,
                      border: `1px solid var(--l-${h.tone}-border)`,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: `var(--l-${h.tone}-text)`,
                    }}>
                      <Icon size={18} />
                    </div>
                    <div>
                      <h3 style={{ fontFamily: "var(--font-display)", fontSize: "0.98rem", fontWeight: 700, margin: "0 0 4px" }}>
                        {h.title}
                      </h3>
                      <p style={{ color: "var(--l-text-secondary)", fontSize: "0.84rem", lineHeight: 1.5, margin: 0 }}>
                        {h.desc}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12, paddingTop: 18, borderTop: "1px solid var(--l-border)" }}>
            <span className="mono-tag" style={{ color: "var(--l-text-muted)" }}>
              JWT + HTTPONLY REFRESH ROTATION
            </span>
            <span className="mono-tag" style={{ color: "var(--l-emerald-text)", fontWeight: 700 }}>
              ROLE-BASED ACCESS CONTROL
            </span>
          </div>
        </section>

        {/* Right Sign-In Form Panel */}
        <section className="auth-form-pane">
          <motion.div
            className="auth-card"
            initial={{ opacity: 0, y: 14, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.35 }}
          >
            <div style={{ textAlign: "center", marginBottom: 26 }}>
              <div style={{
                width: 56,
                height: 56,
                margin: "0 auto 14px",
                background: "var(--l-btn-primary-bg)",
                borderRadius: 16,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                boxShadow: "0 10px 24px rgba(16, 185, 129, 0.24)",
              }}>
                <Hexagon size={28} strokeWidth={2.2} color="#ffffff" />
              </div>
              <h2 style={{ margin: "0 0 6px", fontFamily: "var(--font-display)", fontSize: "1.65rem", fontWeight: 800 }}>
                {shopName ? shopName : "PharmOS"}
              </h2>
              <p style={{ color: "var(--l-text-muted)", fontSize: "0.9rem", margin: 0 }}>
                Sign in to access your pharmacy workspace
              </p>
            </div>

            <form onSubmit={handleSubmit}>
              <div style={{ marginBottom: 18 }}>
                <label
                  htmlFor="login-email"
                  className="mono-tag"
                  style={{ display: "block", fontWeight: 700, color: "var(--l-text-muted)", marginBottom: 8 }}
                >
                  Username or Email
                </label>
                <div style={{ position: "relative" }}>
                  <div style={{ position: "absolute", left: 14, top: "50%", transform: "translateY(-50%)", color: "var(--l-text-muted)", display: "flex" }}>
                    <Mail size={17} />
                  </div>
                  <input
                    id="login-email"
                    type="text"
                    className="auth-input"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    autoFocus
                    placeholder="kushmedical@gmail.com"
                  />
                </div>
              </div>

              <div style={{ marginBottom: 22 }}>
                <label
                  htmlFor="login-password"
                  className="mono-tag"
                  style={{ display: "block", fontWeight: 700, color: "var(--l-text-muted)", marginBottom: 8 }}
                >
                  Password
                </label>
                <div style={{ position: "relative" }}>
                  <div style={{ position: "absolute", left: 14, top: "50%", transform: "translateY(-50%)", color: "var(--l-text-muted)", display: "flex" }}>
                    <Lock size={17} />
                  </div>
                  <input
                    id="login-password"
                    type={showPassword ? "text" : "password"}
                    className="auth-input"
                    style={{ paddingRight: 44 }}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    placeholder="••••••••"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((s) => !s)}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    style={{
                      position: "absolute",
                      right: 10,
                      top: "50%",
                      transform: "translateY(-50%)",
                      background: "transparent",
                      border: "none",
                      color: "var(--l-text-muted)",
                      cursor: "pointer",
                      padding: 6,
                      display: "flex",
                      alignItems: "center",
                    }}
                  >
                    {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                  </button>
                </div>
              </div>

              {error && (
                <motion.div
                  initial={{ opacity: 0, y: -6 }}
                  animate={{ opacity: 1, y: 0 }}
                  style={{
                    background: "var(--l-rose-soft)",
                    color: "var(--l-rose-text)",
                    padding: "11px 14px",
                    borderRadius: 12,
                    fontSize: "0.86rem",
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    marginBottom: 18,
                    border: "1px solid var(--l-rose-border)",
                    fontWeight: 500,
                  }}
                >
                  <AlertCircle size={16} style={{ flexShrink: 0 }} />
                  <span>{error}</span>
                </motion.div>
              )}

              <button
                type="submit"
                className="landing-btn-primary"
                style={{ width: "100%", padding: "13px 20px", fontSize: "0.96rem", cursor: loading ? "wait" : "pointer" }}
                disabled={loading}
              >
                {loading ? "Authenticating..." : <>Sign in to Workspace <ArrowRight size={17} /></>}
              </button>

              <div style={{ marginTop: 22, paddingTop: 18, borderTop: "1px solid var(--l-border)", textAlign: "center", fontSize: "0.88rem", color: "var(--l-text-muted)" }}>
                New pharmacy?{" "}
                <Link to="/register" style={{ color: "var(--l-emerald-text)", fontWeight: 700, textDecoration: "none" }}>
                  Create a shop account
                </Link>
              </div>
            </form>
          </motion.div>
        </section>
      </main>
    </div>
  );
}
