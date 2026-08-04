import { useEffect, useRef, useState } from "react";
import { api } from "../api/client.js";

const STARTER_PROMPTS = [
  "Which medicines expire in the next 30 days?",
  "What's my total spend this month vs last month?",
  "Show me my top 5 best-selling medicines",
  "What's my profit margin on Bacterial Infection medicines vs the shop average?",
  "Which medicines are below their reorder threshold?",
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

function ThinkingIndicator() {
  return (
    <div className="copilot-message copilot-message-assistant">
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
        <span key={name} className="badge auto" style={{ fontSize: 11 }}>
          {TOOL_LABELS[name] || name}
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
      <div className="copilot-bubble">
        {content}
        {!isUser && <ToolCallBadges toolCalls={toolCalls} />}
      </div>
    </div>
  );
}

export default function Copilot() {
  const [messages, setMessages] = useState([]);   // [{role, content, toolCalls}]
  const [input, setInput] = useState("");
  const [history, setHistory] = useState([]);      // opaque, echoed back to backend
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const scrollRef = useRef(null);

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
    <div>
      <div className="card">
        <h2 style={{ marginBottom: 4 }}>🤖 PharmaCopilot</h2>
        <p style={{ color: "#666", fontSize: 13, marginTop: 0 }}>
          Ask questions about your shop's own data — stock, sales, expiry, GST, pricing, drug
          interactions. Every answer is grounded in a real lookup against your data, shown as
          badges below each reply — never guessed.
        </p>
      </div>

      <div className="card copilot-window">
        <div className="copilot-scroll-area">
          {messages.length === 0 && (
            <div className="copilot-empty-state">
              <p style={{ color: "#888", fontSize: 13, marginBottom: 12 }}>
                Try asking something, or pick a starter:
              </p>
              <div className="copilot-starter-chips">
                {STARTER_PROMPTS.map((p) => (
                  <button key={p} className="copilot-chip" onClick={() => sendMessage(p)}>
                    {p}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <Message key={i} role={m.role} content={m.content} toolCalls={m.toolCalls} index={i} />
          ))}

          {loading && <ThinkingIndicator />}
          {error && <p style={{ color: "#b91c1c", fontSize: 13, padding: "0 4px" }}>{error}</p>}
          <div ref={scrollRef} />
        </div>

        <form onSubmit={handleSubmit} className="copilot-input-row">
          <textarea
            rows={1}
            placeholder="Ask about your shop's data..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
          />
          <button type="submit" disabled={loading || !input.trim()}>
            {loading ? "..." : "Send"}
          </button>
        </form>
      </div>

      <style>{`
        .copilot-window { display: flex; flex-direction: column; height: 560px; padding: 0; overflow: hidden; }
        .copilot-scroll-area { flex: 1; overflow-y: auto; padding: 18px; display: flex; flex-direction: column; gap: 10px; }
        .copilot-empty-state { padding: 20px 0; }
        .copilot-starter-chips { display: flex; flex-wrap: wrap; gap: 8px; }
        .copilot-chip {
          background: #f5f5f5; border: 1px solid #e5e5e5; color: #333;
          border-radius: 20px; padding: 8px 14px; font-size: 13px; cursor: pointer;
          transition: background 0.15s ease;
        }
        .copilot-chip:hover { background: #ececec; }

        @keyframes copilotFadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
        .copilot-message { display: flex; animation: copilotFadeIn 0.25s ease; }
        .copilot-message-user { justify-content: flex-end; }
        .copilot-message-assistant { justify-content: flex-start; }
        .copilot-bubble {
          max-width: 78%; padding: 10px 14px; border-radius: 14px; font-size: 14px; line-height: 1.5;
          white-space: pre-wrap;
        }
        .copilot-message-user .copilot-bubble { background: #1c1c1e; color: #fff; border-bottom-right-radius: 4px; }
        .copilot-message-assistant .copilot-bubble { background: #f5f5f5; color: #1c1c1e; border-bottom-left-radius: 4px; }
        .copilot-tool-badges { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 8px; }

        .copilot-thinking { background: #f5f5f5; border-radius: 14px; border-bottom-left-radius: 4px; padding: 12px 16px; display: flex; gap: 4px; }
        .copilot-dot { width: 6px; height: 6px; border-radius: 50%; background: #999; animation: copilotBounce 1.2s infinite ease-in-out; }
        .copilot-dot:nth-child(2) { animation-delay: 0.15s; }
        .copilot-dot:nth-child(3) { animation-delay: 0.3s; }
        @keyframes copilotBounce { 0%, 60%, 100% { transform: translateY(0); opacity: 0.5; } 30% { transform: translateY(-4px); opacity: 1; } }

        .copilot-input-row { display: flex; gap: 8px; padding: 14px 18px; border-top: 1px solid #eee; background: #fff; }
        .copilot-input-row textarea {
          flex: 1; resize: none; font-family: inherit; padding: 10px 12px; max-height: 100px;
        }
      `}</style>
    </div>
  );
}