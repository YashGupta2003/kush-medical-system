import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Sparkles, Send, Bot, User, Calendar, DollarSign, Flame, TrendingUp, Package, Search, AlertTriangle, RefreshCw, Network, ShoppingCart } from "lucide-react";
import { api } from "../api/client.js";

const STARTER_PROMPTS = [
  { icon: <Calendar size={14} />, text: "Which medicines expire in the next 30 days?" },
  { icon: <DollarSign size={14} />, text: "What's my total spend this month vs last month?" },
  { icon: <Flame size={14} />, text: "Show me my top 5 best-selling medicines" },
  { icon: <TrendingUp size={14} />, text: "What's my profit margin on Bacterial Infection medicines vs the shop average?" },
  { icon: <Package size={14} />, text: "Which medicines are below their reorder threshold?" },
];

const TOOL_LABELS = {
  get_expiring_medicines: { label: "Checked expiring medicines", icon: <Calendar size={12} /> },
  get_gst_report: { label: "Pulled GST report", icon: <DollarSign size={12} /> },
  get_monthly_spend: { label: "Checked monthly spend", icon: <DollarSign size={12} /> },
  get_price_changes: { label: "Checked price changes", icon: <TrendingUp size={12} /> },
  get_top_selling: { label: "Checked top sellers", icon: <Flame size={12} /> },
  get_top_medicines_by_spend: { label: "Checked top spend items", icon: <Package size={12} /> },
  get_distributor_breakdown: { label: "Checked distributor breakdown", icon: <Search size={12} /> },
  get_shop_overview: { label: "Checked shop overview", icon: <TrendingUp size={12} /> },
  get_reorder_list: { label: "Checked reorder list", icon: <Package size={12} /> },
  search_medicines: { label: "Searched medicines", icon: <Search size={12} /> },
  get_stock_snapshot: { label: "Checked stock snapshot", icon: <Package size={12} /> },
  check_drug_interactions: { label: "Checked drug interactions", icon: <AlertTriangle size={12} /> },
  find_medicines_for_condition: { label: "Searched by condition", icon: <Search size={12} /> },
  find_substitutes: { label: "Searched substitutes", icon: <RefreshCw size={12} /> },
  get_medicine_graph: { label: "Checked medicine graph", icon: <Network size={12} /> },
  get_profit_margin_analysis: { label: "Analyzed profit margins", icon: <TrendingUp size={12} /> },
  get_recent_sales: { label: "Checked recent sales", icon: <ShoppingCart size={12} /> },
};

const markdownComponents = {
  table: ({ children }) => (
    <div className="copilot-table-wrap"><table className="table">{children}</table></div>
  ),
  th: ({ children }) => <th>{children}</th>,
  td: ({ children }) => <td>{children}</td>,
  strong: ({ children }) => <strong className="copilot-strong">{children}</strong>,
  p: ({ children }) => <p className="copilot-p">{children}</p>,
  ul: ({ children }) => <ul className="copilot-list">{children}</ul>,
  ol: ({ children }) => <ol className="copilot-list">{children}</ol>,
  code: ({ children }) => <code className="copilot-code">{children}</code>,
  a: ({ href, children }) => <a href={href} target="_blank" rel="noreferrer">{children}</a>,
};

function ThinkingIndicator() {
  return (
    <div className="copilot-message copilot-message-assistant">
      <div className="copilot-avatar copilot-avatar-bot copilot-avatar-pulse"><Bot size={16} color="var(--primary-500)" /></div>
      <div className="copilot-thinking">
        <span className="copilot-dot" />
        <span className="copilot-dot" />
        <span className="copilot-dot" />
      </div>
    </div>
  );
}

function ToolCallBadges({ toolCalls }) {
  if (!toolCalls || toolCalls.length === 0) return null;
  const unique = [...new Set(toolCalls.map((t) => t.tool))];
  return (
    <div className="copilot-tool-badges">
      {unique.map((name) => {
        const meta = TOOL_LABELS[name] || { label: `🔧 ${name}`, icon: null };
        return (
          <span key={name} className="copilot-tool-badge">
            {meta.icon} {meta.label}
          </span>
        );
      })}
    </div>
  );
}

function Message({ role, content, toolCalls, index }) {
  const isUser = role === "user";
  return (
    <div
      className={`copilot-message ${isUser ? "copilot-message-user" : "copilot-message-assistant"}`}
      style={{ animationDelay: `${Math.min(index * 30, 200)}ms` }}
    >
      {!isUser && <div className="copilot-avatar copilot-avatar-bot"><Bot size={16} color="var(--primary-500)" /></div>}
      <div className="copilot-bubble">
        {isUser ? (
          content
        ) : (
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
            {content}
          </ReactMarkdown>
        )}
        {!isUser && <ToolCallBadges toolCalls={toolCalls} />}
      </div>
      {isUser && <div className="copilot-avatar copilot-avatar-user"><User size={16} color="var(--info)" /></div>}
    </div>
  );
}

export default function Copilot() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const scrollRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function sendMessage(text) {
    const trimmed = text.trim();
    if (!trimmed || loading) return;

    setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
    setInput("");
    setLoading(true);
    setError(null);

    try {
      const res = await api.sendCopilotMessage(trimmed, history);
      setMessages((prev) => [...prev, { role: "assistant", content: res.reply, toolCalls: res.tool_calls }]);
      setHistory(res.history);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
      textareaRef.current?.focus();
    }
  }

  function handleSubmit(e) {
    e.preventDefault();
    sendMessage(input);
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.2 }}
      className="page-content copilot-page"
    >
      <div className="copilot-hero" style={{ background: "linear-gradient(120deg, var(--bg-card), var(--bg-surface))", border: "1px solid var(--border)" }}>
        <div className="copilot-hero-orb copilot-orb-1" />
        <div className="copilot-hero-orb copilot-orb-2" />
        <div className="copilot-hero-orb copilot-orb-3" />
        <div className="copilot-hero-content">
          <div className="copilot-hero-icon"><Bot size={32} color="var(--primary-500)" /></div>
          <div>
            <h2 className="copilot-hero-title" style={{ color: "var(--text-main)" }}>PharmaCopilot</h2>
            <p className="copilot-hero-subtitle" style={{ color: "var(--text-muted)" }}>
              Ask anything about your shop's stock, sales, expiry, GST, pricing, or drug
              interactions — every answer is grounded in a real lookup against your data.
            </p>
          </div>
        </div>
      </div>

      <div className="copilot-window" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
        <div className="copilot-scroll-area">
          {messages.length === 0 && (
            <div className="copilot-empty-state">
              <div className="copilot-empty-icon"><Sparkles size={40} color="var(--warning)" /></div>
              <p className="copilot-empty-text" style={{ color: "var(--text-muted)" }}>Try asking something, or pick a starter:</p>
              <div className="copilot-starter-chips">
                {STARTER_PROMPTS.map((p) => (
                  <button key={p.text} className="copilot-chip" onClick={() => sendMessage(p.text)} style={{ background: "var(--bg-card)", borderColor: "var(--border)", color: "var(--text-main)" }}>
                    <span>{p.icon}</span> {p.text}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <Message key={i} role={m.role} content={m.content} toolCalls={m.toolCalls} index={i} />
          ))}

          {loading && <ThinkingIndicator />}
          {error && <p className="copilot-error" style={{ color: "var(--danger)" }}>{error}</p>}
          <div ref={scrollRef} />
        </div>

        <form onSubmit={handleSubmit} className="copilot-input-row" style={{ background: "var(--bg-card)", borderTop: "1px solid var(--border)" }}>
          <textarea
            ref={textareaRef}
            rows={1}
            placeholder="Ask about your shop's data..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
            autoFocus
            style={{ background: "var(--bg-surface)", borderColor: "var(--border)", color: "var(--text-main)" }}
          />
          <button type="submit" className="btn btn-primary copilot-send-btn" disabled={loading || !input.trim()}>
            {loading ? <span className="copilot-send-spinner" /> : <><Send size={16} /> Send</>}
          </button>
        </form>
      </div>

      <style>{`
        .copilot-page { display: flex; flex-direction: column; gap: 16px; }

        /* ---------------- Hero banner ---------------- */
        .copilot-hero {
          position: relative; overflow: hidden; border-radius: 16px; padding: 28px 26px;
          box-shadow: 0 8px 30px rgba(0,0,0,0.05);
        }
        .copilot-hero-orb {
          position: absolute; border-radius: 50%; filter: blur(40px); opacity: 0.15;
          animation: copilotFloat 10s ease-in-out infinite;
        }
        .copilot-orb-1 { width: 180px; height: 180px; background: var(--primary-500); top: -60px; right: 40px; }
        .copilot-orb-2 { width: 140px; height: 140px; background: var(--success); bottom: -50px; right: 220px; animation-delay: -3s; }
        .copilot-orb-3 { width: 120px; height: 120px; background: var(--purple); top: 20px; right: 340px; animation-delay: -6s; }
        @keyframes copilotFloat {
          0%, 100% { transform: translate(0,0) scale(1); }
          50% { transform: translate(-14px, 16px) scale(1.08); }
        }
        .copilot-hero-content { position: relative; z-index: 1; display: flex; align-items: center; gap: 18px; }
        .copilot-hero-icon {
          width: 62px; height: 62px; border-radius: 16px; flex-shrink: 0;
          background: var(--bg-surface); border: 1px solid var(--border);
          display: flex; align-items: center; justify-content: center;
          animation: copilotIconBob 3s ease-in-out infinite;
        }
        @keyframes copilotIconBob { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-4px); } }
        .copilot-hero-title { margin: 0 0 4px; font-size: 21px; font-weight: 600; }
        .copilot-hero-subtitle { margin: 0; font-size: 13.5px; max-width: 640px; line-height: 1.5; }

        /* ---------------- Chat window ---------------- */
        .copilot-window {
          display: flex; flex-direction: column; height: 600px; border-radius: 16px;
          overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,0.03);
        }
        .copilot-scroll-area { flex: 1; overflow-y: auto; padding: 22px; display: flex; flex-direction: column; gap: 14px; }

        .copilot-empty-state { padding: 30px 10px; text-align: center; margin: auto; }
        .copilot-empty-icon { display: inline-flex; margin-bottom: 10px; animation: copilotSparkle 2.4s ease-in-out infinite; }
        @keyframes copilotSparkle { 0%, 100% { opacity: 0.6; transform: scale(1) rotate(0deg); } 50% { opacity: 1; transform: scale(1.15) rotate(8deg); } }
        .copilot-empty-text { font-size: 13px; margin-bottom: 16px; }
        .copilot-starter-chips { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; max-width: 560px; margin: 0 auto; }
        .copilot-chip {
          display: flex; align-items: center; gap: 8px;
          border-radius: 22px; padding: 9px 16px; font-size: 13px; cursor: pointer;
          transition: all 0.18s ease; box-shadow: 0 1px 2px rgba(0,0,0,0.03);
        }
        .copilot-chip:hover { transform: translateY(-1px); box-shadow: 0 4px 10px rgba(0,0,0,0.08); opacity: 0.9; }

        @keyframes copilotFadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        .copilot-message { display: flex; align-items: flex-end; gap: 8px; animation: copilotFadeIn 0.3s ease both; }
        .copilot-message-user { justify-content: flex-end; }
        .copilot-message-assistant { justify-content: flex-start; }

        .copilot-avatar {
          width: 32px; height: 32px; border-radius: 50%; flex-shrink: 0;
          display: flex; align-items: center; justify-content: center;
        }
        .copilot-avatar-bot { background: var(--bg-card); border: 1px solid var(--border); }
        .copilot-avatar-user { background: var(--bg-card); border: 1px solid var(--border); }
        .copilot-avatar-pulse { animation: copilotAvatarPulse 1.6s ease-in-out infinite; }
        @keyframes copilotAvatarPulse { 0%, 100% { box-shadow: 0 0 0 0 rgba(14,165,233,0.25); } 50% { box-shadow: 0 0 0 6px rgba(14,165,233,0); } }

        .copilot-bubble {
          max-width: 74%; padding: 12px 16px; border-radius: 16px; font-size: 14px; line-height: 1.55;
        }
        .copilot-message-user .copilot-bubble {
          background: var(--primary-500); color: #fff; border-bottom-right-radius: 4px;
        }
        .copilot-message-assistant .copilot-bubble {
          background: var(--bg-card); color: var(--text-main); border: 1px solid var(--border); border-bottom-left-radius: 4px;
          box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }
        .copilot-p { margin: 0 0 8px; }
        .copilot-p:last-child { margin-bottom: 0; }
        .copilot-strong { font-weight: 700; color: var(--text-main); }
        .copilot-list { margin: 4px 0 8px; padding-left: 20px; }
        .copilot-code { background: var(--bg-surface); padding: 2px 6px; border-radius: 4px; font-size: 12.5px; border: 1px solid var(--border); }
        .copilot-table-wrap { overflow-x: auto; margin: 8px 0; border-radius: 8px; }

        .copilot-tool-badges { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
        .copilot-tool-badge {
          font-size: 11px; padding: 4px 10px; border-radius: 20px; font-weight: 600;
          background: var(--bg-surface); color: var(--info); border: 1px solid var(--border);
          display: flex; align-items: center; gap: 4px;
        }

        .copilot-thinking {
          background: var(--bg-card); border: 1px solid var(--border); border-radius: 16px; border-bottom-left-radius: 4px;
          padding: 13px 18px; display: flex; gap: 5px;
        }
        .copilot-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--text-muted); animation: copilotBounce 1.2s infinite ease-in-out; }
        .copilot-dot:nth-child(2) { animation-delay: 0.15s; }
        .copilot-dot:nth-child(3) { animation-delay: 0.3s; }
        @keyframes copilotBounce { 0%, 60%, 100% { transform: translateY(0); opacity: 0.5; } 30% { transform: translateY(-4px); opacity: 1; } }

        .copilot-error { font-size: 13px; padding: 0 4px; }

        .copilot-input-row { display: flex; gap: 10px; padding: 16px 20px; }
        .copilot-input-row textarea {
          flex: 1; resize: none; font-family: inherit; padding: 11px 14px; max-height: 100px;
          border-radius: 10px; font-size: 14px; transition: border-color 0.15s ease, box-shadow 0.15s ease;
        }
        .copilot-input-row textarea:focus { outline: none; box-shadow: 0 0 0 3px rgba(14,165,233,0.15); }
        .copilot-send-btn {
          display: flex; align-items: center; justify-content: center; gap: 6px; min-width: 90px;
        }
        .copilot-send-spinner {
          width: 14px; height: 14px; border: 2px solid rgba(255,255,255,0.35); border-top-color: #fff;
          border-radius: 50%; animation: copilotSpin 0.7s linear infinite; display: inline-block;
        }
        @keyframes copilotSpin { to { transform: rotate(360deg); } }
      `}</style>
    </motion.div>
  );
}