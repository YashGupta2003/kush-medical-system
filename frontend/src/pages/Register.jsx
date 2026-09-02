import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  Hexagon, Building2, User, Mail, Lock, Phone, MapPin,
  FileText, AlertCircle, CheckCircle, ArrowRight, Eye, EyeOff,
  ChevronLeft, Sparkles, Shield, TrendingUp
} from "lucide-react";
import { useAuth } from "../auth/AuthContext.jsx";
import { api } from "../api/client.js";

// ── Glowing Background ──────────────────────────────────────────────────────
function GlowingBackground() {
  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden", zIndex: 0, pointerEvents: "none" }}>
      <div style={{ position: "absolute", top: "-20%", left: "-10%", width: "50%", height: "50%", background: "radial-gradient(circle, rgba(16,185,129,0.15) 0%, transparent 60%)", filter: "blur(60px)" }} />
      <div style={{ position: "absolute", bottom: "-20%", right: "-10%", width: "50%", height: "50%", background: "radial-gradient(circle, rgba(59,130,246,0.15) 0%, transparent 60%)", filter: "blur(60px)" }} />
    </div>
  );
}

// ── Custom Dark Field ────────────────────────────────────────────────────────
function Field({ label, icon, error, required, ...inputProps }) {
  const [focused, setFocused] = useState(false);
  return (
    <div style={{ marginBottom: 20 }}>
      <label style={{
        display: "block", fontSize: "0.75rem", fontWeight: 700,
        color: "rgba(255,255,255,0.7)", marginBottom: 8,
        textTransform: "uppercase", letterSpacing: "0.05em"
      }}>
        {label} {required && <span style={{ color: "#ef4444" }}>*</span>}
      </label>
      <div style={{ position: "relative" }}>
        {icon && (
          <div style={{
            position: "absolute", left: 14, top: "50%", transform: "translateY(-50%)",
            color: focused ? "#10b981" : "rgba(255,255,255,0.4)", transition: "color 0.2s"
          }}>
            {icon}
          </div>
        )}
        <input
          onFocus={(e) => { setFocused(true); if (inputProps.onFocus) inputProps.onFocus(e); }}
          onBlur={(e) => { setFocused(false); if (inputProps.onBlur) inputProps.onBlur(e); }}
          style={{
            width: "100%",
            background: "rgba(255,255,255,0.03)",
            border: `1px solid ${error ? "#ef4444" : focused ? "#10b981" : "rgba(255,255,255,0.1)"}`,
            borderRadius: 12,
            padding: `12px 16px 12px ${icon ? "40px" : "16px"}`,
            color: "#fff",
            fontSize: "0.95rem",
            outline: "none",
            boxShadow: focused ? (error ? "0 0 0 3px rgba(239,68,68,0.2)" : "0 0 0 3px rgba(16,185,129,0.2)") : "none",
            transition: "all 0.2s"
          }}
          {...inputProps}
        />
      </div>
      {error && (
        <motion.p initial={{ opacity: 0, y: -5 }} animate={{ opacity: 1, y: 0 }} style={{ margin: "6px 0 0", fontSize: "0.8rem", color: "#ef4444", fontWeight: 500 }}>
          {error}
        </motion.p>
      )}
    </div>
  );
}

// ── Main Register page ────────────────────────────────────────────────────────
export default function Register() {
  const navigate = useNavigate();
  const { loginWithTokens } = useAuth();

  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showPassword, setShowPassword] = useState(false);

  const [form, setForm] = useState({
    shop_name: "", owner_name: "", gstin: "", city: "", address: "",
    email: "", phone: "", password: "", confirmPassword: "",
  });
  const [fieldErrors, setFieldErrors] = useState({});

  function set(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
    if (fieldErrors[field]) setFieldErrors((e) => ({ ...e, [field]: null }));
  }

  function validateStep1() {
    const errs = {};
    if (!form.shop_name.trim()) errs.shop_name = "Shop name is required";
    else if (form.shop_name.trim().length < 2) errs.shop_name = "At least 2 characters";
    if (!form.owner_name.trim()) errs.owner_name = "Owner name is required";
    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  }

  function validateStep2() {
    const errs = {};
    if (!form.email.trim()) errs.email = "Email is required";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) errs.email = "Enter a valid email";
    if (!form.password) errs.password = "Password is required";
    else if (form.password.length < 8) errs.password = "Minimum 8 characters";
    if (form.password !== form.confirmPassword) errs.confirmPassword = "Passwords do not match";
    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  }

  function nextStep() {
    if (step === 1 && validateStep1()) setStep(2);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!validateStep2()) return;

    setLoading(true);
    setError(null);
    try {
      const data = await api.register({
        shop_name: form.shop_name.trim(),
        owner_name: form.owner_name.trim(),
        email: form.email.trim().toLowerCase(),
        password: form.password,
        phone: form.phone.trim() || undefined,
        gstin: form.gstin.trim() || undefined,
        city: form.city.trim() || undefined,
        address: form.address.trim() || undefined,
      });

      if (loginWithTokens) {
        await loginWithTokens(data.access_token, data.refresh_token, {
          username: data.username, role: data.role, full_name: data.full_name,
          tenant_id: data.tenant_id, shop_name: data.shop_name,
        });
      }
      setStep(3);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ minHeight: "100vh", display: "flex", background: "#030712", color: "#fff", position: "relative", overflow: "hidden", fontFamily: "var(--font-base)" }}>
      <GlowingBackground />

      {/* ── Left Panel (Branding) ── */}
      <div style={{
        width: "45%", minWidth: 400,
        background: "linear-gradient(150deg, rgba(16,185,129,0.1), rgba(3,7,18,0.8))",
        borderRight: "1px solid rgba(255,255,255,0.05)",
        display: "flex", flexDirection: "column", justifyContent: "center",
        padding: "64px", position: "relative", zIndex: 1,
        backdropFilter: "blur(20px)"
      }} className="hide-on-mobile">
        <Link to="/" style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 60, fontWeight: 800, fontSize: "1.4rem", color: "#fff", textDecoration: "none" }}>
          <div style={{ background: "linear-gradient(135deg, #10b981, #059669)", width: 44, height: 44, borderRadius: 12, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Hexagon size={24} strokeWidth={2.5} />
          </div>
          PharmOS
        </Link>

        <h2 style={{ fontSize: "clamp(2rem, 4vw, 3rem)", fontWeight: 800, lineHeight: 1.1, margin: "0 0 24px", letterSpacing: "-0.03em", fontFamily: "var(--font-display)" }}>
          Start your <span style={{ color: "#10b981" }}>AI journey</span> today.
        </h2>
        <p style={{ color: "rgba(255,255,255,0.7)", lineHeight: 1.7, margin: "0 0 48px", fontSize: "1.1rem" }}>
          Join hundreds of pharmacies upgrading to autonomous, intelligent operations.
        </p>

        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          {[
            { icon: <Sparkles size={20} />, text: "AI Bill Extraction in seconds" },
            { icon: <Shield size={20} />, text: "Real-time Drug Interaction Guard" },
            { icon: <TrendingUp size={20} />, text: "Automated Demand Forecasting" },
          ].map((item, i) => (
            <motion.div key={i} initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 + (i * 0.1) }} style={{ display: "flex", alignItems: "center", gap: 16 }}>
              <div style={{ width: 40, height: 40, borderRadius: 10, background: "rgba(16,185,129,0.1)", color: "#10b981", display: "flex", alignItems: "center", justifyContent: "center" }}>
                {item.icon}
              </div>
              <span style={{ fontSize: "1.05rem", fontWeight: 600, color: "rgba(255,255,255,0.9)" }}>{item.text}</span>
            </motion.div>
          ))}
        </div>

        <div style={{ marginTop: "auto", paddingTop: 60, opacity: 0.6, fontSize: "0.9rem" }}>
          Already have an account?{" "}
          <Link to="/login" style={{ color: "#10b981", fontWeight: 700, textDecoration: "none" }}>Sign In &rarr;</Link>
        </div>
      </div>

      {/* ── Right Panel (Form) ── */}
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: "40px", overflowY: "auto", position: "relative", zIndex: 1 }}>
        <div style={{ width: "100%", maxWidth: 440 }}>
          <AnimatePresence mode="wait">

            {/* STEP 1 */}
            {step === 1 && (
              <motion.div key="step1" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} transition={{ duration: 0.3 }}>
                <div style={{ marginBottom: 40 }}>
                  <div style={{ display: "inline-flex", gap: 8, marginBottom: 16, fontSize: "0.8rem", fontWeight: 700, color: "rgba(255,255,255,0.5)", textTransform: "uppercase", letterSpacing: "0.1em" }}>
                    <span style={{ color: "#10b981" }}>Step 1</span> <span>/</span> <span>2</span>
                  </div>
                  <h1 style={{ margin: "0 0 12px", fontSize: "2rem", fontWeight: 800, fontFamily: "var(--font-display)" }}>Tell us about your shop</h1>
                  <p style={{ margin: 0, color: "rgba(255,255,255,0.6)", fontSize: "1rem" }}>This will be your identity on the platform.</p>
                </div>

                <div>
                  <Field label="Shop Name" icon={<Building2 size={18} />} placeholder="e.g. Sharma Medicals" value={form.shop_name} onChange={(e) => set("shop_name", e.target.value)} error={fieldErrors.shop_name} required />
                  <Field label="Owner / Proprietor Name" icon={<User size={18} />} placeholder="e.g. Rajesh Sharma" value={form.owner_name} onChange={(e) => set("owner_name", e.target.value)} error={fieldErrors.owner_name} required />
                  <Field label="City" icon={<MapPin size={18} />} placeholder="e.g. Jaipur" value={form.city} onChange={(e) => set("city", e.target.value)} />
                  <Field label="GSTIN (optional)" icon={<FileText size={18} />} placeholder="e.g. 27AAAAA0000A1Z5" value={form.gstin} onChange={(e) => set("gstin", e.target.value)} />

                  <motion.button
                    style={{ width: "100%", padding: "16px", marginTop: 16, fontSize: "1rem", fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center", gap: 10, background: "linear-gradient(135deg, #10b981, #059669)", color: "#fff", border: "none", borderRadius: 12, cursor: "pointer", boxShadow: "0 8px 20px rgba(16,185,129,0.3)" }}
                    whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} onClick={nextStep} type="button"
                  >
                    Continue to Account <ArrowRight size={20} />
                  </motion.button>
                  
                  <p style={{ textAlign: "center", marginTop: 24, fontSize: "0.9rem", color: "rgba(255,255,255,0.5)" }}>
                    Already registered? <Link to="/login" style={{ color: "#10b981", fontWeight: 700, textDecoration: "none" }}>Sign In</Link>
                  </p>
                </div>
              </motion.div>
            )}

            {/* STEP 2 */}
            {step === 2 && (
              <motion.div key="step2" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} transition={{ duration: 0.3 }}>
                <div style={{ marginBottom: 40 }}>
                  <button onClick={() => setStep(1)} style={{ background: "none", border: "none", cursor: "pointer", display: "flex", alignItems: "center", gap: 8, color: "rgba(255,255,255,0.6)", fontWeight: 600, fontSize: "0.9rem", padding: 0, marginBottom: 24, transition: "color 0.2s" }} onMouseOver={e => e.currentTarget.style.color="#fff"} onMouseOut={e => e.currentTarget.style.color="rgba(255,255,255,0.6)"}>
                    <ChevronLeft size={18} /> Back
                  </button>
                  <div style={{ display: "inline-flex", gap: 8, marginBottom: 16, fontSize: "0.8rem", fontWeight: 700, color: "rgba(255,255,255,0.5)", textTransform: "uppercase", letterSpacing: "0.1em" }}>
                    <span style={{ color: "#10b981" }}>Step 2</span> <span>/</span> <span>2</span>
                  </div>
                  <h1 style={{ margin: "0 0 12px", fontSize: "2rem", fontWeight: 800, fontFamily: "var(--font-display)" }}>Create your account</h1>
                  <p style={{ margin: 0, color: "rgba(255,255,255,0.6)", fontSize: "1rem" }}>Setting up account for <strong style={{ color: "#fff" }}>{form.shop_name}</strong></p>
                </div>

                <form onSubmit={handleSubmit}>
                  <Field label="Email Address" icon={<Mail size={18} />} type="email" placeholder="owner@yourshop.com" value={form.email} onChange={(e) => set("email", e.target.value)} error={fieldErrors.email} required />
                  <Field label="WhatsApp / Phone (optional)" icon={<Phone size={18} />} type="tel" placeholder="+91 98765 43210" value={form.phone} onChange={(e) => set("phone", e.target.value)} />

                  <div style={{ marginBottom: 20 }}>
                    <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 700, color: "rgba(255,255,255,0.7)", marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                      Password <span style={{ color: "#ef4444" }}>*</span>
                    </label>
                    <div style={{ position: "relative" }}>
                      <div style={{ position: "absolute", left: 14, top: "50%", transform: "translateY(-50%)", color: "rgba(255,255,255,0.4)" }}>
                        <Lock size={18} />
                      </div>
                      <input
                        type={showPassword ? "text" : "password"}
                        placeholder="Min 8 characters"
                        value={form.password}
                        onChange={(e) => set("password", e.target.value)}
                        style={{ width: "100%", background: "rgba(255,255,255,0.03)", border: `1px solid ${fieldErrors.password ? "#ef4444" : "rgba(255,255,255,0.1)"}`, borderRadius: 12, padding: "12px 44px", color: "#fff", fontSize: "0.95rem", outline: "none", transition: "all 0.2s" }}
                        onFocus={e => e.target.style.borderColor = "#10b981"}
                        onBlur={e => e.target.style.borderColor = fieldErrors.password ? "#ef4444" : "rgba(255,255,255,0.1)"}
                        required
                      />
                      <button type="button" onClick={() => setShowPassword(!showPassword)} style={{ position: "absolute", right: 14, top: "50%", transform: "translateY(-50%)", background: "none", border: "none", cursor: "pointer", color: "rgba(255,255,255,0.4)", padding: 0 }}>
                        {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                      </button>
                    </div>
                    {fieldErrors.password && <p style={{ margin: "6px 0 0", fontSize: "0.8rem", color: "#ef4444", fontWeight: 500 }}>{fieldErrors.password}</p>}
                  </div>

                  <Field label="Confirm Password" icon={<Lock size={18} />} type="password" placeholder="Repeat password" value={form.confirmPassword} onChange={(e) => set("confirmPassword", e.target.value)} error={fieldErrors.confirmPassword} required />

                  {error && (
                    <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} style={{ background: "rgba(239,68,68,0.1)", color: "#ef4444", padding: 16, borderRadius: 12, fontSize: "0.9rem", display: "flex", alignItems: "center", gap: 10, marginBottom: 24, border: "1px solid rgba(239,68,68,0.2)" }}>
                      <AlertCircle size={18} />
                      <span>{error}</span>
                    </motion.div>
                  )}

                  <motion.button
                    style={{ width: "100%", padding: "16px", marginTop: 8, fontSize: "1rem", fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center", gap: 10, background: "linear-gradient(135deg, #10b981, #059669)", color: "#fff", border: "none", borderRadius: 12, cursor: "pointer", boxShadow: "0 8px 20px rgba(16,185,129,0.3)", opacity: loading ? 0.7 : 1 }}
                    whileHover={!loading ? { scale: 1.02 } : {}} whileTap={!loading ? { scale: 0.98 } : {}} type="submit" disabled={loading}
                  >
                    {loading ? "Creating your account..." : "Complete Registration"}
                    {!loading && <CheckCircle size={20} />}
                  </motion.button>
                  <p style={{ textAlign: "center", marginTop: 24, fontSize: "0.85rem", color: "rgba(255,255,255,0.4)", lineHeight: 1.6 }}>
                    By registering you agree to our Terms of Service. Your data is stored securely.
                  </p>
                </form>
              </motion.div>
            )}

            {/* STEP 3: SUCCESS */}
            {step === 3 && (
              <motion.div key="step3" initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.4, type: "spring" }} style={{ textAlign: "center" }}>
                <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ delay: 0.2, type: "spring", stiffness: 200 }} style={{ width: 90, height: 90, margin: "0 auto 32px", background: "linear-gradient(135deg, #10b981, #059669)", borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", boxShadow: "0 12px 30px rgba(16, 185, 129, 0.4)" }}>
                  <CheckCircle size={44} />
                </motion.div>
                <h1 style={{ margin: "0 0 16px", fontSize: "2.2rem", fontWeight: 800, fontFamily: "var(--font-display)" }}>Welcome to PharmOS! 🎉</h1>
                <p style={{ color: "rgba(255,255,255,0.7)", lineHeight: 1.7, margin: "0 auto 40px", maxWidth: 380, fontSize: "1.05rem" }}>
                  Your account for <strong style={{ color: "#fff" }}>{form.shop_name}</strong> is ready. Next, upload your medicine rate list to initialize your AI.
                </p>
                <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                  <motion.button
                    style={{ padding: "18px", fontSize: "1.1rem", fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center", gap: 10, background: "#fff", color: "#030712", border: "none", borderRadius: 14, cursor: "pointer", boxShadow: "0 8px 24px rgba(255,255,255,0.15)" }}
                    whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }} onClick={() => navigate("/setup")}
                  >
                    Upload Medicine List <ArrowRight size={20} />
                  </motion.button>
                  <motion.button
                    style={{ padding: "16px", fontSize: "0.95rem", fontWeight: 600, background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 14, cursor: "pointer", color: "rgba(255,255,255,0.8)" }}
                    whileHover={{ scale: 1.02, background: "rgba(255,255,255,0.08)" }} onClick={() => navigate("/")}
                  >
                    Skip for now &rarr; Go to Dashboard
                  </motion.button>
                </div>
              </motion.div>
            )}

          </AnimatePresence>
        </div>
      </div>
      
      {/* Mobile-only background overlay */}
      <style dangerouslySetInnerHTML={{__html: `
        @media (max-width: 768px) {
          .hide-on-mobile { display: none !important; }
        }
      `}} />
    </div>
  );
}
