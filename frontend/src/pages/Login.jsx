import { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext.jsx";
import { motion } from "framer-motion";
import { Hexagon, Lock, User, AlertCircle, Mail } from "lucide-react";
import { api } from "../api/client.js";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [shopName, setShopName] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      // 1. Lookup the shop and tenant_id using the email
      const shopInfo = await api.lookupShop(email);
      setShopName(shopInfo.shop_name);

      // 2. Login using the email, password, and tenant_id
      await login(email, password, shopInfo.tenant_id);
      
      const redirectTo = location.state?.from || "/";
      navigate(redirectTo, { replace: true });
    } catch (err) {
      setError(err.message || "Failed to login. Please check your credentials.");
    } finally {
      setLoading(false);
    }
  }

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1,
        delayChildren: 0.2
      }
    }
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 300, damping: 24 } }
  };

  return (
    <div style={{
      minHeight: "100vh",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      position: "relative",
      overflow: "hidden",
      background: "var(--bg-app)"
    }}>
      {/* Dynamic Background */}
      <div style={{
        position: "absolute",
        inset: 0,
        zIndex: 0,
        background: "radial-gradient(circle at 50% 0%, var(--primary-900) 0%, transparent 60%), radial-gradient(circle at 100% 100%, var(--primary-800) 0%, transparent 50%)",
        opacity: 0.15
      }} />
      
      <motion.div 
        className="card card-raised"
        style={{ width: "100%", maxWidth: 400, position: "relative", zIndex: 1, padding: "var(--space-8)" }}
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4, ease: [0.4, 0, 0.2, 1] }}
      >
        <motion.div variants={containerVariants} initial="hidden" animate="visible">
          <motion.div variants={itemVariants} style={{ textAlign: "center", marginBottom: "var(--space-6)" }}>
            <div style={{ 
              width: 64, height: 64, margin: "0 auto", 
              background: "linear-gradient(135deg, var(--primary-500), var(--primary-700))",
              borderRadius: "var(--radius-xl)",
              display: "flex", alignItems: "center", justifyContent: "center",
              color: "#fff",
              boxShadow: "0 10px 20px rgba(20, 184, 166, 0.2)"
            }}>
              <Hexagon size={32} strokeWidth={2} />
            </div>
            <h2 style={{ margin: "var(--space-4) 0 var(--space-1)", fontFamily: "var(--font-display)", fontSize: "var(--text-2xl)", color: "var(--text-main)" }}>
              {shopName ? shopName : "PharmOS"}
            </h2>
            <p style={{ color: "var(--text-muted)", fontSize: "var(--text-sm)", margin: 0 }}>
              Sign in to your dashboard
            </p>
          </motion.div>

          <form onSubmit={handleSubmit}>
            <motion.div variants={itemVariants} style={{ marginBottom: "var(--space-4)" }}>
              <label style={{ display: "block", fontSize: "var(--text-xs)", fontWeight: 600, color: "var(--text-muted)", marginBottom: "var(--space-2)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                Username or Email
              </label>
              <div style={{ position: "relative" }}>
                <div style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }}>
                  <Mail size={16} />
                </div>
                <input 
                  type="text"
                  className="input" 
                  style={{ paddingLeft: 36 }} 
                  value={email} 
                  onChange={(e) => setEmail(e.target.value)} 
                  required 
                  autoFocus 
                  placeholder="Enter your email"
                />
              </div>
            </motion.div>

            <motion.div variants={itemVariants} style={{ marginBottom: "var(--space-6)" }}>
              <label style={{ display: "block", fontSize: "var(--text-xs)", fontWeight: 600, color: "var(--text-muted)", marginBottom: "var(--space-2)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                Password
              </label>
              <div style={{ position: "relative" }}>
                <div style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }}>
                  <Lock size={16} />
                </div>
                <input 
                  type="password" 
                  className="input" 
                  style={{ paddingLeft: 36 }} 
                  value={password} 
                  onChange={(e) => setPassword(e.target.value)} 
                  required 
                  placeholder="••••••••"
                />
              </div>
            </motion.div>

            {error && (
              <motion.div 
                initial={{ opacity: 0, y: -10 }} 
                animate={{ opacity: 1, y: 0 }}
                style={{ 
                  background: "var(--danger-bg)", 
                  color: "var(--danger-text)", 
                  padding: "var(--space-3)", 
                  borderRadius: "var(--radius-md)",
                  fontSize: "var(--text-sm)",
                  display: "flex", alignItems: "center", gap: 8,
                  marginBottom: "var(--space-4)",
                  border: "1px solid var(--danger-border)"
                }}
              >
                <AlertCircle size={16} />
                <span>{error}</span>
              </motion.div>
            )}

            <motion.div variants={itemVariants}>
              <button 
                type="submit" 
                className="btn btn-primary" 
                style={{ width: "100%", padding: "var(--space-3)", fontSize: "var(--text-base)", fontWeight: 600 }} 
                disabled={loading}
              >
                {loading ? "Authenticating..." : "Sign in to Workspace"}
              </button>
            </motion.div>
          </form>
        </motion.div>
      </motion.div>
    </div>
  );
}