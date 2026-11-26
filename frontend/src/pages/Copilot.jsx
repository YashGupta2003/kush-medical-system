import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  AlertTriangle,
  ArrowUpRight,
  Bot,
  Calendar,
  Check,
  Copy,
  Database,
  DollarSign,
  FileText,
  Flame,
  Network,
  Package,
  RefreshCw,
  RotateCcw,
  Search,
  Send,
  ShieldCheck,
  ShoppingCart,
  Sparkles,
  TrendingUp,
  User,
  Zap,
} from "lucide-react";
import { api } from "../api/client.js";
import "../styles/copilot.css";

const STARTER_PROMPTS = [
  {
    id: "expiry",
    category: "Expiry Guard",
    title: "30-Day Near-Expiry Scan",
    text: "Which medicines expire in the next 30 days?",
    tone: "rose",
    icon: Calendar,
  },
  {
    id: "spend",
    category: "Spend & Cashflow",
    title: "Monthly Spend Comparison",
    text: "What's my total spend this month vs last month?",
    tone: "sky",
    icon: DollarSign,
  },
  {
    id: "topsellers",
    category: "Sales Velocity",
    title: "Top 5 Fast Movers",
    text: "Show me my top 5 best-selling medicines",
    tone: "amber",
    icon: Flame,
  },
  {
    id: "margins",
    category: "Profit Analyzer",
    title: "Margin Benchmark",
    text: "What's my profit margin on Bacterial Infection medicines vs the shop average?",
    tone: "teal",
    icon: TrendingUp,
  },
  {
    id: "reorder",
    category: "Smart Restock",
    title: "Low-Stock Threshold Audit",
    text: "Which medicines are below their reorder threshold?",
    tone: "violet",
    icon: Package,
  },
  {
    id: "ddi",
    category: "Clinical Safety",
    title: "Salt Interaction Check",
    text: "Check drug interactions between Aspirin and Warfarin",
    tone: "rose",
    icon: AlertTriangle,
  },
];

const FOLLOW_UP_SUGGESTIONS = [
  "Break this down by distributor",
  "Which items need urgent reordering?",
  "Summarize my GST report for this month",
];

const TOOL_LABELS = {
  get_expiring_medicines: { label: "Checked expiring medicines", icon: Calendar },
  get_gst_report: { label: "Pulled GST report", icon: FileText },
  get_monthly_spend: { label: "Checked monthly spend", icon: DollarSign },
  get_price_changes: { label: "Checked price changes", icon: TrendingUp },
  get_top_selling: { label: "Checked top sellers", icon: Flame },
  get_top_medicines_by_spend: { label: "Checked top spend items", icon: Package },
  get_distributor_breakdown: { label: "Checked distributor breakdown", icon: Search },
  get_shop_overview: { label: "Checked shop overview", icon: TrendingUp },
  get_reorder_list: { label: "Checked reorder list", icon: Package },
  search_medicines: { label: "Searched medicines", icon: Search },
  get_stock_snapshot: { label: "Checked stock snapshot", icon: Package },
  check_drug_interactions: { label: "Checked drug interactions", icon: AlertTriangle },
  find_medicines_for_condition: { label: "Searched by condition", icon: Search },
  find_substitutes: { label: "Searched substitutes", icon: RefreshCw },
  get_medicine_graph: { label: "Checked PharmaGraph", icon: Network },
  get_profit_margin_analysis: { label: "Analyzed profit margins", icon: TrendingUp },
  get_recent_sales: { label: "Checked recent sales", icon: ShoppingCart },
  get_uncollected_prescriptions: { label: "Checked pending Rx", icon: FileText },
  explain_anomaly: { label: "Explained anomaly", icon: Zap },
};

const TELEMETRY_PILLS = [
  { id: "get_expiring_medicines", name: "Expiry Watch" },
  { id: "get_profit_margin_analysis", name: "Margins" },
  { id: "get_gst_report", name: "GST Slabs" },
  { id: "get_reorder_list", name: "Reorder Queue" },
  { id: "get_top_selling", name: "Top Velocity" },
  { id: "check_drug_interactions", name: "DDI Graph" },
  { id: "get_monthly_spend", name: "Monthly Spend" },
  { id: "find_substitutes", name: "Salt Substitutes" },
];

const markdownComponents = {
  table: ({ children }) => (
    <div className="copilot-table-wrap">
      <table>{children}</table>
    </div>
  ),
  th: ({ children }) => <th>{children}</th>,
  td: ({ children }) => <td>{children}</td>,
  strong: ({ children }) => <strong className="copilot-strong">{children}</strong>,
  p: ({ children }) => <p className="copilot-p">{children}</p>,
  ul: ({ children }) => <ul className="copilot-list">{children}</ul>,
  ol: ({ children }) => <ol className="copilot-list">{children}</ol>,
  code: ({ children }) => <code className="copilot-code">{children}</code>,
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noreferrer">
      {children}
    </a>
  ),
};

function ToolCallBadges({ toolCalls }) {
  if (!toolCalls || toolCalls.length === 0) return null;
  const unique = [...new Set(toolCalls.map((t) => t.tool))];
  return (
    <div className="copilot-tool-ribbon" aria-label="Verified shop tools used">
      {unique.map((name) => {
        const meta = TOOL_LABELS[name];
        const IconComp = meta?.icon || Zap;
        return (
          <span key={name} className="copilot-tool-pill">
            <IconComp size={12} />
            {meta ? meta.label : name}
          </span>
        );
      })}
    </div>
  );
}

function Message({ role, content, toolCalls, index }) {
  const isUser = role === "user";
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    if (!navigator.clipboard || !content) return;
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      // Clipboard API unavailable in restricted contexts
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, delay: Math.min(index * 0.02, 0.12) }}
      className={`copilot-msg ${isUser ? "copilot-msg-user" : "copilot-msg-assistant"}`}
    >
      {!isUser && (
        <div className="copilot-avatar copilot-avatar-bot" aria-hidden="true">
          <Bot size={17} />
        </div>
      )}

      {isUser ? (
        <div className="copilot-bubble-user">{content}</div>
      ) : (
        <div className="copilot-card-assistant">
          <div className="copilot-assistant-meta">
            <span className="copilot-assistant-label">
              <ShieldCheck size={13} /> Grounded Shop Reply
            </span>
            <button
              type="button"
              className="copilot-copy-btn"
              onClick={handleCopy}
              aria-label="Copy response"
            >
              {copied ? <Check size={12} /> : <Copy size={12} />}
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
            {content}
          </ReactMarkdown>
          <ToolCallBadges toolCalls={toolCalls} />
        </div>
      )}

      {isUser && (
        <div className="copilot-avatar copilot-avatar-user" aria-hidden="true">
          <User size={16} />
        </div>
      )}
    </motion.div>
  );
}

function ThinkingIndicator() {
  return (
    <div className="copilot-msg copilot-msg-assistant">
      <div className="copilot-avatar copilot-avatar-bot copilot-avatar-pulse" aria-hidden="true">
        <Bot size={17} />
      </div>
      <div className="copilot-thinking-card">
        <div className="copilot-dots" aria-hidden="true">
          <span className="copilot-dot" />
          <span className="copilot-dot" />
          <span className="copilot-dot" />
        </div>
        <span>Querying shop records & verifying tools...</span>
      </div>
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

  // Auto-resize composer textarea cleanly as user types multiline queries
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 130)}px`;
  }, [input]);

  const activeToolsSet = useMemo(() => {
    const set = new Set();
    for (const msg of messages) {
      for (const tc of msg.toolCalls || []) {
        if (tc.tool) set.add(tc.tool);
      }
    }
    return set;
  }, [messages]);

  async function sendMessage(text) {
    const trimmed = text.trim();
    if (!trimmed || loading) return;

    setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
    setInput("");
    setLoading(true);
    setError(null);

    try {
      const res = await api.sendCopilotMessage(trimmed, history);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: res.reply, toolCalls: res.tool_calls },
      ]);
      setHistory(res.history || []);
    } catch (err) {
      setError(err.message || "Could not reach PharmaCopilot right now.");
    } finally {
      setLoading(false);
      textareaRef.current?.focus();
    }
  }

  function handleReset() {
    if (loading) return;
    setMessages([]);
    setHistory([]);
    setError(null);
    setInput("");
    textareaRef.current?.focus();
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

  const lastMessage = messages[messages.length - 1];
  const showFollowups = !loading && lastMessage?.role === "assistant";

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.22 }}
      className="page-content copilot-shell"
    >
      {/* Top Studio Header */}
      <header className="copilot-topbar">
        <div className="copilot-brand">
          <div className="copilot-crest">
            <Bot size={26} />
          </div>
          <div>
            <div className="copilot-title-row">
              <h2 className="copilot-title">PharmaCopilot</h2>
              <span className="copilot-live-pill">
                <span className="copilot-pulse-dot" /> Live Shop Intelligence
              </span>
            </div>
            <p className="copilot-subtitle">
              Ask anything about inventory, expiry risk, distributor pricing, GST slabs, profit
              margins, or clinical salt interactions — grounded directly in real database lookups.
            </p>
          </div>
        </div>

        <div className="copilot-header-actions">
          <div className="copilot-model-chip">
            <Database size={14} style={{ color: "var(--cp-accent)" }} />
            <span>19 Live Tools Wired</span>
          </div>
          <button
            type="button"
            className="copilot-reset-btn"
            onClick={handleReset}
            disabled={loading || messages.length === 0}
          >
            <RotateCcw size={14} /> New Chat
          </button>
        </div>
      </header>

      {/* Main Two-Column Studio */}
      <div className="copilot-workspace">
        {/* Left Playbook & Tool Telemetry Rail */}
        <aside className="copilot-rail">
          <div className="copilot-rail-card">
            <div className="copilot-rail-heading">
              <span>Quick Playbooks</span>
              <Sparkles size={13} style={{ color: "var(--cp-amber)" }} />
            </div>
            <div className="copilot-playbook-list">
              {STARTER_PROMPTS.map((item) => {
                const IconComp = item.icon;
                return (
                  <button
                    key={item.id}
                    type="button"
                    className="copilot-playbook-btn"
                    onClick={() => sendMessage(item.text)}
                    disabled={loading}
                  >
                    <div className={`copilot-playbook-icon ${item.tone}`}>
                      <IconComp size={15} />
                    </div>
                    <div>
                      <div className="copilot-playbook-title">{item.title}</div>
                      <div className="copilot-playbook-desc">{item.text}</div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="copilot-rail-card">
            <div className="copilot-rail-heading">
              <span>Session Tool Telemetry</span>
              <Zap size={13} style={{ color: "var(--cp-accent)" }} />
            </div>
            <div className="copilot-tool-telemetry">
              {TELEMETRY_PILLS.map((tool) => {
                const active = activeToolsSet.has(tool.id);
                return (
                  <span
                    key={tool.id}
                    className={`copilot-telemetry-pill ${active ? "active" : ""}`}
                  >
                    {active && <Check size={11} />}
                    {tool.name}
                  </span>
                );
              })}
            </div>
            <div className="copilot-rail-links">
              <Link to="/expiry" className="copilot-quick-link">
                Expiry <ArrowUpRight size={12} />
              </Link>
              <Link to="/profit" className="copilot-quick-link">
                Margins <ArrowUpRight size={12} />
              </Link>
              <Link to="/gst" className="copilot-quick-link">
                GST <ArrowUpRight size={12} />
              </Link>
              <Link to="/smart-purchase" className="copilot-quick-link">
                Restock <ArrowUpRight size={12} />
              </Link>
            </div>
          </div>
        </aside>

        {/* Right Primary Chat Canvas */}
        <section className="copilot-canvas" aria-label="PharmaCopilot conversation">
          <div className="copilot-canvas-header">
            <div className="copilot-canvas-status">
              <ShieldCheck size={15} style={{ color: "var(--cp-accent)" }} />
              <span>Zero-Hallucination Tool Execution Active</span>
            </div>
            <span className="copilot-turn-pill">
              {messages.length === 0
                ? "Ready for prompt"
                : `${Math.ceil(messages.length / 2)} turn${messages.length > 2 ? "s" : ""}`}
            </span>
          </div>

          <div className="copilot-scroll-area">
            {messages.length === 0 && (
              <div className="copilot-welcome">
                <div className="copilot-welcome-orb">
                  <Sparkles size={30} />
                </div>
                <h3>Ask anything about your pharmacy</h3>
                <p>
                  PharmaCopilot executes real SQL &amp; graph lookups against your store before
                  responding — complete with structured tables and verified tool badges.
                </p>

                <div className="copilot-pillars">
                  <span className="copilot-pillar-tag">
                    <ShieldCheck size={13} style={{ color: "var(--cp-accent)" }} /> Tool-Verified Data
                  </span>
                  <span className="copilot-pillar-tag">
                    <TrendingUp size={13} style={{ color: "var(--cp-sky)" }} /> GST &amp; Margin Math
                  </span>
                  <span className="copilot-pillar-tag">
                    <Network size={13} style={{ color: "var(--cp-violet)" }} /> PharmaGraph DDI Check
                  </span>
                </div>

                <div className="copilot-prompt-grid">
                  {STARTER_PROMPTS.map((item) => {
                    const IconComp = item.icon;
                    return (
                      <button
                        key={`welcome-${item.id}`}
                        type="button"
                        className="copilot-prompt-card"
                        onClick={() => sendMessage(item.text)}
                      >
                        <div className={`copilot-playbook-icon ${item.tone}`}>
                          <IconComp size={15} />
                        </div>
                        <div>
                          <div className="copilot-prompt-cat">{item.category}</div>
                          <div className="copilot-prompt-q">{item.text}</div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {messages.map((m, i) => (
              <Message
                key={i}
                role={m.role}
                content={m.content}
                toolCalls={m.toolCalls}
                index={i}
              />
            ))}

            {showFollowups && (
              <div className="copilot-followups">
                {FOLLOW_UP_SUGGESTIONS.map((q) => (
                  <button
                    key={q}
                    type="button"
                    className="copilot-followup-btn"
                    onClick={() => sendMessage(q)}
                    disabled={loading}
                  >
                    <Sparkles size={12} style={{ color: "var(--cp-accent)" }} />
                    {q}
                  </button>
                ))}
              </div>
            )}

            {loading && <ThinkingIndicator />}

            {error && (
              <div className="copilot-error-banner" role="alert">
                <span>{error}</span>
                <button
                  type="button"
                  className="copilot-copy-btn"
                  onClick={() => setError(null)}
                >
                  Dismiss
                </button>
              </div>
            )}

            <div ref={scrollRef} />
          </div>

          <div className="copilot-composer-wrap">
            <form onSubmit={handleSubmit} className="copilot-composer">
              <textarea
                ref={textareaRef}
                rows={1}
                placeholder="Ask about expiring batches, best margins, distributor spend, GST, or drug interactions..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={loading}
                autoFocus
              />
              <button
                type="submit"
                className="copilot-send-btn"
                disabled={loading || !input.trim()}
              >
                {loading ? (
                  <>
                    <span className="copilot-send-spinner" /> Thinking
                  </>
                ) : (
                  <>
                    <Send size={15} /> Send
                  </>
                )}
              </button>
            </form>
            <div className="copilot-composer-hint">
              <span>Press Enter to send &bull; Shift + Enter for new line</span>
              <span>Owner-scoped live queries only</span>
            </div>
          </div>
        </section>
      </div>
    </motion.div>
  );
}
