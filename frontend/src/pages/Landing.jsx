import { motion, useScroll, useTransform } from "framer-motion";
import { Link } from "react-router-dom";
import {
  Hexagon, Scan, Bot, BarChart2, Shield, TrendingUp,
  Package, Snowflake, Network, CheckCircle, ArrowRight, Star,
  Clock, IndianRupee, FileText, Quote, Zap
} from "lucide-react";

// --- Data ---
const FEATURES = [
  { icon: <Scan size={24} />, title: "AI Bill Digitization", desc: "Photograph any distributor invoice. OCR extracts every line item automatically.", color: "#10b981" },
  { icon: <Bot size={24} />, title: "PharmaCopilot", desc: "Ask anything. 'Which medicine is running low?' Powered by Groq AI.", color: "#8b5cf6" },
  { icon: <BarChart2 size={24} />, title: "Predictive Analytics", desc: "Demand forecasting, anomaly detection, and smart reorder suggestions.", color: "#f59e0b" },
  { icon: <Shield size={24} />, title: "Interaction Guard", desc: "Automatically checks if medicines in the same cart have dangerous interactions.", color: "#ef4444" },
  { icon: <Package size={24} />, title: "Stock & Expiry", desc: "Real-time stock levels, low-stock alerts, and near-expiry warnings.", color: "#3b82f6" },
  { icon: <Network size={24} />, title: "PharmaGraph", desc: "Knowledge graph of medicines, salts, and conditions. Find substitutes instantly.", color: "#06b6d4" },
];

const REVIEWS = [
  { name: "Rajesh Kumar", shop: "Sharma Medicals, Jaipur", text: "PharmOS completely transformed our shop. We used to spend hours typing 100-item distributor bills into our old software. Now we just take a photo and the AI does it instantly. Unbelievable.", rating: 5 },
  { name: "Dr. Anjali Desai", shop: "Sanjeevani Pharmacy, Mumbai", text: "The drug interaction guard is a lifesaver. It alerted my staff when a customer accidentally bought two conflicting BP medications. Highly professional system.", rating: 5 },
  { name: "Vikram Singh", shop: "Apex Medicos, Delhi", text: "The demand forecasting helped us reduce our expired stock waste by 80%. It literally tells us exactly what to order and when. Best investment for our business.", rating: 5 },
];

const STEPS = [
  { step: "1", title: "Register Your Shop", desc: "Enter your shop name and GSTIN. Done in 60 seconds." },
  { step: "2", title: "Upload Excel List", desc: "Import your existing rate list. We match it automatically." },
  { step: "3", title: "Start Using AI", desc: "Upload bills, check stock, and get AI insights immediately." },
];

// --- Components ---
function GlowingBackground() {
  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden", zIndex: 0, pointerEvents: "none" }}>
      <div style={{ position: "absolute", top: "-20%", left: "-10%", width: "50%", height: "50%", background: "radial-gradient(circle, rgba(16,185,129,0.15) 0%, transparent 60%)", filter: "blur(60px)" }} />
      <div style={{ position: "absolute", bottom: "-20%", right: "-10%", width: "50%", height: "50%", background: "radial-gradient(circle, rgba(59,130,246,0.15) 0%, transparent 60%)", filter: "blur(60px)" }} />
    </div>
  );
}

function ReviewCard({ review, index }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ delay: index * 0.15, duration: 0.6 }}
      whileHover={{ y: -5, scale: 1.02 }}
      style={{
        background: "rgba(255,255,255,0.03)",
        border: "1px solid rgba(255,255,255,0.1)",
        borderRadius: "var(--radius-2xl)",
        padding: "var(--space-8)",
        position: "relative",
        backdropFilter: "blur(20px)",
        boxShadow: "0 20px 40px rgba(0,0,0,0.2)",
        flex: "1 1 300px",
        display: "flex", flexDirection: "column",
      }}
    >
      <Quote size={40} color="rgba(255,255,255,0.1)" style={{ position: "absolute", top: 24, right: 24 }} />
      <div style={{ display: "flex", gap: 4, marginBottom: 16 }}>
        {[...Array(review.rating)].map((_, i) => <Star key={i} size={16} fill="#f59e0b" color="#f59e0b" />)}
      </div>
      <p style={{ color: "rgba(255,255,255,0.85)", fontSize: "var(--text-base)", lineHeight: 1.7, marginBottom: 24, flex: 1, fontStyle: "italic" }}>
        "{review.text}"
      </p>
      <div>
        <div style={{ color: "#fff", fontWeight: 700, fontSize: "var(--text-base)" }}>{review.name}</div>
        <div style={{ color: "var(--primary-400)", fontSize: "var(--text-sm)" }}>{review.shop}</div>
      </div>
    </motion.div>
  );
}

export default function Landing() {
  const { scrollYProgress } = useScroll();
  const yPos = useTransform(scrollYProgress, [0, 1], [0, -100]);

  return (
    <div style={{ minHeight: "100vh", background: "#030712", color: "#fff", fontFamily: "var(--font-base)", overflowX: "hidden" }}>
      
      {/* ── NAVBAR ── */}
      <nav style={{
        position: "fixed", top: 0, left: 0, right: 0, zIndex: 100,
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "16px clamp(24px, 5vw, 64px)",
        background: "rgba(3, 7, 18, 0.6)",
        backdropFilter: "blur(24px)",
        borderBottom: "1px solid rgba(255,255,255,0.05)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, color: "#fff", fontWeight: 800, fontSize: "1.3rem" }}>
          <div style={{
            background: "linear-gradient(135deg, #10b981, #059669)",
            width: 38, height: 38, borderRadius: 12,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <Hexagon size={22} strokeWidth={2.5} />
          </div>
          PharmOS
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <Link to="/login" style={{ color: "rgba(255,255,255,0.8)", fontWeight: 600, fontSize: "var(--text-sm)", textDecoration: "none", transition: "color 0.2s" }} onMouseOver={e => e.currentTarget.style.color = "#fff"} onMouseOut={e => e.currentTarget.style.color = "rgba(255,255,255,0.8)"}>
            Sign In
          </Link>
          <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
            <Link to="/register" style={{
              padding: "10px 24px", borderRadius: "var(--radius-full)",
              background: "#fff", color: "#030712", fontWeight: 700, fontSize: "var(--text-sm)",
              textDecoration: "none", boxShadow: "0 4px 14px rgba(255,255,255,0.15)",
            }}>
              Register Free
            </Link>
          </motion.div>
        </div>
      </nav>

      {/* ── HERO ── */}
      <section style={{ position: "relative", minHeight: "100vh", display: "flex", flexDirection: "column", justifyContent: "center", padding: "120px clamp(24px, 5vw, 64px) 80px", overflow: "hidden" }}>
        <GlowingBackground />
        
        {/* Abstract Grid Pattern */}
        <div style={{
          position: "absolute", inset: 0, opacity: 0.03, zIndex: 0, pointerEvents: "none",
          backgroundImage: "linear-gradient(rgba(255,255,255,1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,1) 1px, transparent 1px)",
          backgroundSize: "40px 40px"
        }} />

        <div style={{ position: "relative", zIndex: 1, maxWidth: 900, margin: "0 auto", textAlign: "center" }}>
          <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.5, ease: "easeOut" }} style={{
            display: "inline-flex", alignItems: "center", gap: 8,
            background: "rgba(16, 185, 129, 0.1)", color: "#10b981",
            padding: "8px 20px", borderRadius: "var(--radius-full)",
            fontSize: "var(--text-sm)", fontWeight: 700,
            border: "1px solid rgba(16, 185, 129, 0.2)", marginBottom: 32,
          }}>
            <Zap size={16} fill="currentColor" />
            The Next Generation Pharmacy OS
          </motion.div>

          <motion.h1 initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, delay: 0.1, ease: "easeOut" }} style={{
            fontSize: "clamp(2.5rem, 6vw, 4.5rem)", fontWeight: 800, lineHeight: 1.1, margin: "0 0 24px", letterSpacing: "-0.03em", fontFamily: "var(--font-display)"
          }}>
            Manage Your Pharmacy with <br />
            <span style={{ background: "linear-gradient(135deg, #34d399, #10b981)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
              Superhuman AI
            </span>
          </motion.h1>

          <motion.p initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, delay: 0.2, ease: "easeOut" }} style={{
            fontSize: "clamp(1rem, 2vw, 1.25rem)", color: "rgba(255,255,255,0.7)", lineHeight: 1.6, maxWidth: 700, margin: "0 auto 48px"
          }}>
            Upload a bill photo and watch AI extract every item instantly. Complete with drug interaction guards, demand forecasting, and autonomous stock management. 
          </motion.p>

          <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, delay: 0.3, ease: "easeOut" }} style={{ display: "flex", gap: 16, justifyContent: "center", flexWrap: "wrap" }}>
            <Link to="/register" style={{
              display: "inline-flex", alignItems: "center", gap: 10,
              padding: "18px 40px", borderRadius: "var(--radius-full)",
              background: "linear-gradient(135deg, #10b981, #059669)",
              color: "#fff", fontWeight: 700, fontSize: "var(--text-lg)",
              textDecoration: "none", boxShadow: "0 10px 30px rgba(16, 185, 129, 0.3)",
              transition: "transform 0.2s, box-shadow 0.2s",
            }}
            onMouseOver={e => e.currentTarget.style.transform = "translateY(-2px)"}
            onMouseOut={e => e.currentTarget.style.transform = "translateY(0)"}>
              Open Your Free Shop Account <ArrowRight size={20} />
            </Link>
          </motion.div>
        </div>

        {/* Realistic Dashboard Mockup */}
        <motion.div initial={{ opacity: 0, y: 100 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 1, delay: 0.5, ease: "easeOut" }} style={{
          position: "relative", zIndex: 1, marginTop: 80, width: "100%", maxWidth: 1000, margin: "80px auto 0",
          background: "#0f172a", border: "1px solid rgba(255,255,255,0.1)",
          borderRadius: "20px 20px 0 0", height: 400, borderBottom: "none",
          boxShadow: "0 -20px 60px rgba(0,0,0,0.5), 0 0 0 8px rgba(255,255,255,0.02)", overflow: "hidden", display: "flex"
        }}>
           {/* Sidebar */}
           <div style={{ width: 220, background: "#020617", borderRight: "1px solid rgba(255,255,255,0.05)", padding: 20, display: "flex", flexDirection: "column", gap: 16 }}>
             <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#10b981", fontWeight: 700, marginBottom: 20 }}>
               <Hexagon size={20} /> PharmOS
             </div>
             {[1, 2, 3, 4, 5].map(i => (
               <div key={i} style={{ height: 32, borderRadius: 6, background: i === 1 ? "rgba(16,185,129,0.1)" : "transparent", display: "flex", alignItems: "center", padding: "0 12px", color: i === 1 ? "#10b981" : "rgba(255,255,255,0.4)", fontSize: 13, fontWeight: 600 }}>
                 {i === 1 ? "Dashboard" : i === 2 ? "Inventory" : i === 3 ? "Billing" : i === 4 ? "AI Copilot" : "Settings"}
               </div>
             ))}
           </div>
           
           {/* Main Area */}
           <div style={{ flex: 1, padding: 30, display: "flex", flexDirection: "column", gap: 24 }}>
             <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
               <div>
                 <div style={{ fontSize: 20, fontWeight: 700, color: "#fff", marginBottom: 4 }}>Welcome back, Rajesh!</div>
                 <div style={{ fontSize: 13, color: "rgba(255,255,255,0.5)" }}>Your pharmacy is performing 15% better this week.</div>
               </div>
               <div style={{ padding: "8px 16px", background: "#10b981", borderRadius: 8, color: "#fff", fontSize: 13, fontWeight: 600 }}>
                 + Upload Bill (AI)
               </div>
             </div>
             
             {/* Stats Cards */}
             <div style={{ display: "flex", gap: 16 }}>
               {[
                 { label: "Today's Sales", value: "₹24,500", trend: "+12%" },
                 { label: "Low Stock Items", value: "14", trend: "-3" },
                 { label: "Pending Bills", value: "0", trend: "All Cleared" }
               ].map((stat, i) => (
                 <div key={i} style={{ flex: 1, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.05)", borderRadius: 12, padding: 16 }}>
                   <div style={{ fontSize: 12, color: "rgba(255,255,255,0.5)", marginBottom: 8 }}>{stat.label}</div>
                   <div style={{ fontSize: 24, fontWeight: 700, color: "#fff", marginBottom: 8 }}>{stat.value}</div>
                   <div style={{ fontSize: 12, color: "#10b981" }}>{stat.trend}</div>
                 </div>
               ))}
             </div>
             
             {/* Fake Table */}
             <div style={{ flex: 1, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)", borderRadius: 12, overflow: "hidden" }}>
               <div style={{ display: "flex", padding: "12px 16px", borderBottom: "1px solid rgba(255,255,255,0.05)", fontSize: 12, color: "rgba(255,255,255,0.4)", fontWeight: 600 }}>
                 <div style={{ flex: 2 }}>Distributor</div>
                 <div style={{ flex: 1 }}>Items</div>
                 <div style={{ flex: 1 }}>Amount</div>
                 <div style={{ flex: 1 }}>Status</div>
               </div>
               {[
                 { dist: "Apollo Distributors", items: 45, amt: "₹12,450", status: "AI Processed" },
                 { dist: "Sun Pharma Direct", items: 12, amt: "₹4,200", status: "AI Processed" },
               ].map((row, i) => (
                 <div key={i} style={{ display: "flex", padding: "16px", borderBottom: "1px solid rgba(255,255,255,0.02)", fontSize: 13, color: "#fff", alignItems: "center" }}>
                   <div style={{ flex: 2, fontWeight: 600 }}>{row.dist}</div>
                   <div style={{ flex: 1, color: "rgba(255,255,255,0.6)" }}>{row.items} lines</div>
                   <div style={{ flex: 1, fontWeight: 600 }}>{row.amt}</div>
                   <div style={{ flex: 1 }}>
                     <span style={{ padding: "4px 8px", background: "rgba(16,185,129,0.15)", color: "#10b981", borderRadius: 4, fontSize: 11, fontWeight: 700 }}>
                       {row.status}
                     </span>
                   </div>
                 </div>
               ))}
             </div>
           </div>
           
           {/* Fade out bottom to blend with background */}
           <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: 150, background: "linear-gradient(to bottom, transparent, #030712)" }} />
        </motion.div>
      </section>

      {/* ── LOGOS ── */}
      <section style={{ borderTop: "1px solid rgba(255,255,255,0.05)", borderBottom: "1px solid rgba(255,255,255,0.05)", padding: "40px 0", background: "rgba(255,255,255,0.01)" }}>
        <p style={{ textAlign: "center", color: "rgba(255,255,255,0.4)", fontSize: "var(--text-sm)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 24 }}>Trusted by top pharmacies across India</p>
        <div style={{ display: "flex", justifyContent: "center", gap: "clamp(30px, 8vw, 80px)", flexWrap: "wrap", opacity: 0.5 }}>
           {["Apollo Pharmacy", "MedPlus", "Wellness Forever", "NetMeds", "Tata 1mg", "PharmEasy"].map(name => (
             <span key={name} style={{ fontSize: "1.2rem", fontWeight: 800, fontFamily: "var(--font-display)" }}>{name}</span>
           ))}
        </div>
      </section>

      {/* ── FEATURES GRID ── */}
      <section style={{ padding: "120px clamp(24px, 5vw, 64px)", position: "relative" }}>
        <div style={{ maxWidth: 1200, margin: "0 auto" }}>
          <div style={{ textAlign: "center", marginBottom: 80 }}>
            <h2 style={{ fontSize: "clamp(2rem, 4vw, 3rem)", fontWeight: 800, margin: "0 0 16px", fontFamily: "var(--font-display)" }}>Enterprise Power. <br/><span style={{ color: "#10b981" }}>Built for the Local Chemist.</span></h2>
            <p style={{ color: "rgba(255,255,255,0.6)", fontSize: "var(--text-lg)", maxWidth: 600, margin: "0 auto" }}>We give your shop the same artificial intelligence technology used by billion-dollar hospital networks.</p>
          </div>
          
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 32 }}>
            {FEATURES.map((f, i) => (
              <motion.div
                key={f.title}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-50px" }}
                transition={{ delay: i * 0.1, duration: 0.5 }}
                whileHover={{ y: -10, boxShadow: `0 20px 40px ${f.color}15` }}
                style={{
                  background: "rgba(255,255,255,0.02)",
                  border: "1px solid rgba(255,255,255,0.05)",
                  borderRadius: "var(--radius-2xl)",
                  padding: "var(--space-8)",
                  position: "relative", overflow: "hidden"
                }}
              >
                <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 4, background: f.color, opacity: 0.8 }} />
                <div style={{
                  width: 56, height: 56, borderRadius: "var(--radius-xl)", background: `${f.color}15`,
                  display: "flex", alignItems: "center", justifyContent: "center", color: f.color, marginBottom: 24
                }}>
                  {f.icon}
                </div>
                <h3 style={{ fontSize: "1.4rem", fontWeight: 800, marginBottom: 12 }}>{f.title}</h3>
                <p style={{ color: "rgba(255,255,255,0.6)", fontSize: "var(--text-base)", lineHeight: 1.6, margin: 0 }}>{f.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ── TESTIMONIALS ── */}
      <section style={{ padding: "120px clamp(24px, 5vw, 64px)", background: "linear-gradient(to bottom, #030712, #064e3b, #030712)", position: "relative" }}>
        <div style={{ maxWidth: 1200, margin: "0 auto" }}>
          <div style={{ textAlign: "center", marginBottom: 80 }}>
            <h2 style={{ fontSize: "clamp(2rem, 4vw, 3rem)", fontWeight: 800, margin: "0 0 16px", fontFamily: "var(--font-display)" }}>Loved by Shop Owners</h2>
            <p style={{ color: "rgba(255,255,255,0.7)", fontSize: "var(--text-lg)", maxWidth: 600, margin: "0 auto" }}>Don't just take our word for it. Hear from the businesses we've transformed.</p>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 32, justifyContent: "center" }}>
            {REVIEWS.map((review, i) => (
              <ReviewCard key={i} review={review} index={i} />
            ))}
          </div>
        </div>
      </section>

      {/* ── HOW IT WORKS ── */}
      <section style={{ padding: "120px clamp(24px, 5vw, 64px)", position: "relative" }}>
        <div style={{ maxWidth: 800, margin: "0 auto" }}>
          <div style={{ textAlign: "center", marginBottom: 64 }}>
            <h2 style={{ fontSize: "clamp(2rem, 4vw, 3rem)", fontWeight: 800, margin: "0 0 16px", fontFamily: "var(--font-display)" }}>Up and Running in Minutes</h2>
            <p style={{ color: "rgba(255,255,255,0.6)", fontSize: "var(--text-lg)", margin: 0 }}>No IT team required. Our beautiful setup wizard handles everything.</p>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 32, position: "relative" }}>
            <div style={{ position: "absolute", top: 0, bottom: 0, left: 32, width: 2, background: "rgba(255,255,255,0.1)", zIndex: 0 }} />
            {STEPS.map((s, i) => (
              <motion.div
                key={s.step}
                initial={{ opacity: 0, x: -30 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true, margin: "-50px" }}
                transition={{ delay: i * 0.2, duration: 0.5 }}
                style={{ display: "flex", gap: 32, alignItems: "flex-start", position: "relative", zIndex: 1 }}
              >
                <div style={{
                  width: 64, height: 64, borderRadius: "50%", background: "#10b981", color: "#000",
                  display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 800, fontSize: "1.5rem", flexShrink: 0,
                  boxShadow: "0 0 0 8px #030712, 0 0 20px rgba(16,185,129,0.5)"
                }}>
                  {s.step}
                </div>
                <div style={{ background: "rgba(255,255,255,0.03)", padding: "var(--space-6)", borderRadius: "var(--radius-xl)", border: "1px solid rgba(255,255,255,0.05)", flex: 1 }}>
                  <h3 style={{ fontSize: "1.4rem", fontWeight: 800, marginBottom: 8 }}>{s.title}</h3>
                  <p style={{ color: "rgba(255,255,255,0.6)", fontSize: "var(--text-base)", margin: 0 }}>{s.desc}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ── */}
      <section style={{ padding: "120px clamp(24px, 5vw, 64px)", textAlign: "center", background: "linear-gradient(to top, rgba(16,185,129,0.1), #030712)" }}>
        <motion.div initial={{ opacity: 0, scale: 0.9 }} whileInView={{ opacity: 1, scale: 1 }} viewport={{ once: true }} style={{ maxWidth: 800, margin: "0 auto" }}>
          <h2 style={{ fontSize: "clamp(2.5rem, 6vw, 4rem)", fontWeight: 900, margin: "0 0 24px", fontFamily: "var(--font-display)", letterSpacing: "-0.03em" }}>
            Ready for the Future?
          </h2>
          <p style={{ color: "rgba(255,255,255,0.7)", fontSize: "var(--text-xl)", marginBottom: 48 }}>
            Join the network of pharmacies transforming their operations with AI.
          </p>
          <Link to="/register" style={{
            display: "inline-flex", alignItems: "center", gap: 12,
            padding: "20px 48px", borderRadius: "var(--radius-full)",
            background: "#fff", color: "#030712", fontWeight: 800, fontSize: "1.2rem",
            textDecoration: "none", boxShadow: "0 10px 40px rgba(255,255,255,0.2)",
            transition: "transform 0.2s"
          }}
          onMouseOver={e => e.currentTarget.style.transform = "scale(1.05)"}
          onMouseOut={e => e.currentTarget.style.transform = "scale(1)"}>
            Start Free Trial <ArrowRight size={24} />
          </Link>
        </motion.div>
      </section>

      {/* ── FOOTER ── */}
      <footer style={{ padding: "40px clamp(24px, 5vw, 64px)", background: "#000", display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 24, borderTop: "1px solid rgba(255,255,255,0.1)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 800, color: "#10b981", fontSize: "1.2rem" }}>
          <Hexagon size={20} />
          PharmOS
        </div>
        <div style={{ color: "rgba(255,255,255,0.4)", fontSize: "var(--text-sm)" }}>
          © 2026 PharmOS Tech. Highly Scalable Multi-Tenant Architecture.
        </div>
      </footer>
    </div>
  );
}
