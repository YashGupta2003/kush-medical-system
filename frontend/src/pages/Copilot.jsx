import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "../api/client.js";

const STARTER_PROMPTS = [
  { icon: "📅", text: "Which medicines expire in the next 30 days?" },
  { icon: "💰", text: "What's my total spend this month vs last month?" },
  { icon: "🔥", text: "Show me my top 5 best-selling medicines" },
  { icon: "📈", text: "What's my profit margin on Bacterial Infection medicines vs the shop average?" },
  { icon: "📦", text: "Which medicines are below their reorder threshold?" },
];

const TOOL_LABELS = {
  get_expiring_medicines: "📅 Checked expiring medicines",
  get_gst_report: "🧾 Pulled GST report",
  get_monthly_spend: "💰 Checked monthly spend",
  get_price_changes: "📈 Checked price changes",
  get_top_selling: "🔥 Checked top sellers",
  get_top_medicines_by_spend: "💊 Checked top spend items",
  get_distributor_breakdown: "🏢 Checked distributor breakdown",
  get_shop_overview: "📊 Checked shop overview",
  get_reorder_list: "📦 Checked reorder list",
  search_medicines: "🔍 Searched medicines",
  get_stock_snapshot: "📦 Checked stock snapshot",
  check_drug_interactions: "⚠️ Checked drug interactions",
  find_medicines_for_condition: "💊 Searched by condition",
  find_substitutes: "🔄 Searched substitutes",
  get_medicine_graph: "🕸️ Checked medicine graph",
  get_profit_margin_analysis: "📈 Analyzed profit margins",
  get_recent_sales: "🛒 Checked recent sales",
};

// ---------------------------------------------------------------------------
// Markdown rendering - maps the model's markdown (bold, tables, lists) onto
// this app's existing visual language instead of plain react-markdown
// defaults, so a reply table looks like every other table in the app.
// ---------------------------------------------------------------------------
const markdownComponents = {
  table: ({ children }) => (
    <div className="copilot-table-wrap"><table>{children}</table></div>
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
      <div className="copilot-avatar copilot-avatar-bot copilot-avatar-pulse">🤖</div>
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
      {unique.map((name) => (
        <span key={name} className="copilot-tool-badge">
          {TOOL_LABELS[name] || `🔧 ${name}`}
        </span>
      ))}
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
      {!isUser && <div className="copilot-avatar copilot-avatar-bot">🤖</div>}
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
      {isUser && <div className="copilot-avatar copilot-avatar-user">🧑</div>}
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
    <div className="copilot-page">
      <div className="copilot-hero">
        <div className="copilot-hero-orb copilot-orb-1" />
        <div className="copilot-hero-orb copilot-orb-2" />
        <div className="copilot-hero-orb copilot-orb-3" />
        <div className="copilot-hero-content">
          <div className="copilot-hero-icon">🤖</div>
          <div>
            <h2 className="copilot-hero-title">PharmaCopilot</h2>
            <p className="copilot-hero-subtitle">
              Ask anything about your shop's stock, sales, expiry, GST, pricing, or drug
              interactions — every answer is grounded in a real lookup against your data.
            </p>
          </div>
        </div>
      </div>

      <div className="copilot-window">
        <div className="copilot-scroll-area">
          {messages.length === 0 && (
            <div className="copilot-empty-state">
              <div className="copilot-empty-icon">✨</div>
              <p className="copilot-empty-text">Try asking something, or pick a starter:</p>
              <div className="copilot-starter-chips">
                {STARTER_PROMPTS.map((p) => (
                  <button key={p.text} className="copilot-chip" onClick={() => sendMessage(p.text)}>
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
          {error && <p className="copilot-error">{error}</p>}
          <div ref={scrollRef} />
        </div>

        <form onSubmit={handleSubmit} className="copilot-input-row">
          <textarea
            ref={textareaRef}
            rows={1}
            placeholder="Ask about your shop's data..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
            autoFocus
          />
          <button type="submit" className="copilot-send-btn" disabled={loading || !input.trim()}>
            {loading ? <span className="copilot-send-spinner" /> : "Send ↗"}
          </button>
        </form>
      </div>

      <style>{`
        .copilot-page { display: flex; flex-direction: column; gap: 16px; }

        /* ---------------- Hero banner ---------------- */
        .copilot-hero {
          position: relative; overflow: hidden; border-radius: 16px; padding: 28px 26px;
          background: linear-gradient(120deg, #14141a, #24242e 60%, #1c1c1e);
          box-shadow: 0 8px 30px rgba(0,0,0,0.18);
        }
        .copilot-hero-orb {
          position: absolute; border-radius: 50%; filter: blur(40px); opacity: 0.55;
          animation: copilotFloat 10s ease-in-out infinite;
        }
        .copilot-orb-1 { width: 180px; height: 180px; background: #60a5fa; top: -60px; right: 40px; }
        .copilot-orb-2 { width: 140px; height: 140px; background: #34d399; bottom: -50px; right: 220px; animation-delay: -3s; }
        .copilot-orb-3 { width: 120px; height: 120px; background: #a78bfa; top: 20px; right: 340px; animation-delay: -6s; }
        @keyframes copilotFloat {
          0%, 100% { transform: translate(0,0) scale(1); }
          50% { transform: translate(-14px, 16px) scale(1.08); }
        }
        .copilot-hero-content { position: relative; z-index: 1; display: flex; align-items: center; gap: 18px; }
        .copilot-hero-icon {
          font-size: 34px; width: 62px; height: 62px; border-radius: 16px; flex-shrink: 0;
          background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.14);
          display: flex; align-items: center; justify-content: center;
          animation: copilotIconBob 3s ease-in-out infinite;
        }
        @keyframes copilotIconBob { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-4px); } }
        .copilot-hero-title { color: #fff; margin: 0 0 4px; font-size: 21px; }
        .copilot-hero-subtitle { color: #cfcfd6; margin: 0; font-size: 13.5px; max-width: 640px; line-height: 1.5; }

        /* ---------------- Chat window ---------------- */
        .copilot-window {
          display: flex; flex-direction: column; height: 600px; border-radius: 16px;
          background: #fbfbfc; border: 1px solid #ececef; overflow: hidden;
          box-shadow: 0 2px 12px rgba(0,0,0,0.05);
        }
        .copilot-scroll-area { flex: 1; overflow-y: auto; padding: 22px; display: flex; flex-direction: column; gap: 14px; }

        .copilot-empty-state { padding: 30px 10px; text-align: center; margin: auto; }
        .copilot-empty-icon { font-size: 38px; margin-bottom: 10px; animation: copilotSparkle 2.4s ease-in-out infinite; }
        @keyframes copilotSparkle { 0%, 100% { opacity: 0.6; transform: scale(1) rotate(0deg); } 50% { opacity: 1; transform: scale(1.15) rotate(8deg); } }
        .copilot-empty-text { color: #888; font-size: 13px; margin-bottom: 16px; }
        .copilot-starter-chips { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; max-width: 560px; margin: 0 auto; }
        .copilot-chip {
          display: flex; align-items: center; gap: 8px;
          background: #fff; border: 1px solid #e5e5e5; color: #333;
          border-radius: 22px; padding: 9px 16px; font-size: 13px; cursor: pointer;
          transition: all 0.18s ease; box-shadow: 0 1px 2px rgba(0,0,0,0.03);
        }
        .copilot-chip:hover { background: #1c1c1e; color: #fff; border-color: #1c1c1e; transform: translateY(-1px); box-shadow: 0 4px 10px rgba(0,0,0,0.15); }

        @keyframes copilotFadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        .copilot-message { display: flex; align-items: flex-end; gap: 8px; animation: copilotFadeIn 0.3s ease both; }
        .copilot-message-user { justify-content: flex-end; }
        .copilot-message-assistant { justify-content: flex-start; }

        .copilot-avatar {
          width: 30px; height: 30px; border-radius: 50%; flex-shrink: 0;
          display: flex; align-items: center; justify-content: center; font-size: 15px;
        }
        .copilot-avatar-bot { background: linear-gradient(135deg, #1c1c1e, #3a3a3c); }
        .copilot-avatar-user { background: #e0f2fe; }
        .copilot-avatar-pulse { animation: copilotAvatarPulse 1.6s ease-in-out infinite; }
        @keyframes copilotAvatarPulse { 0%, 100% { box-shadow: 0 0 0 0 rgba(28,28,30,0.25); } 50% { box-shadow: 0 0 0 6px rgba(28,28,30,0); } }

        .copilot-bubble {
          max-width: 74%; padding: 12px 16px; border-radius: 16px; font-size: 14px; line-height: 1.55;
        }
        .copilot-message-user .copilot-bubble {
          background: linear-gradient(135deg, #1c1c1e, #323236); color: #fff; border-bottom-right-radius: 4px;
        }
        .copilot-message-assistant .copilot-bubble {
          background: #fff; color: #1c1c1e; border: 1px solid #ececef; border-bottom-left-radius: 4px;
          box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }
        .copilot-p { margin: 0 0 8px; }
        .copilot-p:last-child { margin-bottom: 0; }
        .copilot-strong { color: #0f172a; font-weight: 700; }
        .copilot-list { margin: 4px 0 8px; padding-left: 20px; }
        .copilot-code { background: #f1f1f3; padding: 1px 5px; border-radius: 4px; font-size: 12.5px; }
        .copilot-table-wrap { overflow-x: auto; margin: 8px 0; border-radius: 8px; border: 1px solid #eee; }
        .copilot-table-wrap table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
        .copilot-table-wrap th {
          background: #f7f7f8; text-align: left; padding: 8px 10px; font-weight: 600;
          border-bottom: 1px solid #eee; white-space: nowrap;
        }
        .copilot-table-wrap td { padding: 7px 10px; border-bottom: 1px solid #f3f3f4; white-space: nowrap; }
        .copilot-table-wrap tr:last-child td { border-bottom: none; }

        .copilot-tool-badges { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
        .copilot-tool-badge {
          font-size: 11px; padding: 3px 9px; border-radius: 20px; font-weight: 600;
          background: #eef2ff; color: #4338ca; border: 1px solid #e0e7ff;
        }

        .copilot-thinking {
          background: #fff; border: 1px solid #ececef; border-radius: 16px; border-bottom-left-radius: 4px;
          padding: 13px 18px; display: flex; gap: 5px;
        }
        .copilot-dot { width: 6px; height: 6px; border-radius: 50%; background: #a3a3a8; animation: copilotBounce 1.2s infinite ease-in-out; }
        .copilot-dot:nth-child(2) { animation-delay: 0.15s; }
        .copilot-dot:nth-child(3) { animation-delay: 0.3s; }
        @keyframes copilotBounce { 0%, 60%, 100% { transform: translateY(0); opacity: 0.5; } 30% { transform: translateY(-4px); opacity: 1; } }

        .copilot-error { color: #b91c1c; font-size: 13px; padding: 0 4px; }

        .copilot-input-row { display: flex; gap: 10px; padding: 16px 20px; border-top: 1px solid #eee; background: #fff; }
        .copilot-input-row textarea {
          flex: 1; resize: none; font-family: inherit; padding: 11px 14px; max-height: 100px;
          border-radius: 10px; border: 1px solid #ddd; font-size: 14px; transition: border-color 0.15s ease, box-shadow 0.15s ease;
        }
        .copilot-input-row textarea:focus { outline: none; border-color: #1c1c1e; box-shadow: 0 0 0 3px rgba(28,28,30,0.08); }
        .copilot-send-btn {
          border-radius: 10px; padding: 0 20px; font-weight: 600; display: flex; align-items: center;
          justify-content: center; min-width: 76px;
        }
        .copilot-send-spinner {
          width: 14px; height: 14px; border: 2px solid rgba(255,255,255,0.35); border-top-color: #fff;
          border-radius: 50%; animation: copilotSpin 0.7s linear infinite; display: inline-block;
        }
        @keyframes copilotSpin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}