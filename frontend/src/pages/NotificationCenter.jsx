import { useEffect, useRef, useState } from "react";
import { api } from "../api/client.js";
import { motion, AnimatePresence } from "framer-motion";
import { Bell, Info, AlertTriangle, ShieldAlert, Check, CheckCircle2 } from "lucide-react";

/**
 * NotificationCenter — Priority 1
 *
 * A bell icon + unread badge in the NavBar, opening a floating panel
 * listing recent notifications with mark-as-read functionality.
 *
 * Follows the project's existing pattern of inline <style> at the bottom
 * of the component, using shared .card/.badge CSS classes from index.css.
 *
 * Polling: unread count is polled every 30s (cheap endpoint, single integer).
 * Full notification list is fetched only when the panel is opened.
 */

const SEVERITY_CONFIG = {
  info: { bg: "var(--primary-50, #eff6ff)", border: "var(--primary-200, #bfdbfe)", icon: Info, text: "var(--primary-700, #1d4ed8)" },
  warning: { bg: "var(--warning-50, #fffbeb)", border: "var(--warning-200, #fde68a)", icon: AlertTriangle, text: "var(--warning-700, #92400e)" },
  critical: { bg: "var(--danger-50, #fef2f2)", border: "var(--danger-200, #fecaca)", icon: ShieldAlert, text: "var(--danger-700, #991b1b)" },
};

const TYPE_LABELS = {
  adherence_overdue: "Adherence",
  anomaly_flagged: "Anomaly",
  low_stock_crossed: "Low Stock",
  credit_overdue: "Credit",
  trust_chain_tamper: "TrustChain",
  near_expiry: "Expiry",
  daily_digest: "Digest",
  system: "System",
};

function NotifItem({ notif, onRead }) {
  const config = SEVERITY_CONFIG[notif.severity] || SEVERITY_CONFIG.info;
  const IconComponent = config.icon;
  const timeAgo = formatTimeAgo(notif.created_at);

  return (
    <motion.div
      initial={{ opacity: 0, y: 5 }}
      animate={{ opacity: 1, y: 0 }}
      layout
      className="notif-item"
      style={{
        background: notif.is_read ? "var(--bg-surface, #fff)" : config.bg,
        borderLeft: `3px solid ${notif.is_read ? "var(--border-color, #e5e7eb)" : config.border}`,
        opacity: notif.is_read ? 0.7 : 1,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 6 }}>
            <IconComponent size={16} style={{ color: config.text }} />
            <span className="badge" style={{
              background: notif.is_read ? "var(--bg-hover)" : config.bg, 
              color: notif.is_read ? "var(--text-muted)" : config.text, 
              border: `1px solid ${notif.is_read ? "var(--border-color)" : config.border}`,
              fontSize: 10, padding: "2px 8px", borderRadius: "100px", fontWeight: 600
            }}>
              {TYPE_LABELS[notif.notification_type] || notif.notification_type}
            </span>
            <span style={{ fontSize: 11, color: "var(--text-muted, #94a3b8)", fontWeight: 500 }}>{timeAgo}</span>
          </div>
          <div style={{ fontSize: 14, fontWeight: 600, color: "var(--text-main, #1e293b)", marginTop: 4, lineHeight: 1.4 }}>
            {notif.title}
          </div>
          <div style={{ fontSize: 13, color: "var(--text-muted, #64748b)", marginTop: 4, lineHeight: 1.5 }}>
            {notif.body}
          </div>
        </div>
        {!notif.is_read && (
          <button
            onClick={(e) => { e.stopPropagation(); onRead(notif.id); }}
            className="notif-read-btn"
            title="Mark as read"
          >
            <Check size={16} />
          </button>
        )}
      </div>
    </motion.div>
  );
}

function formatTimeAgo(iso) {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export function NotificationBell() {
  const [unreadCount, setUnreadCount] = useState(0);
  const [isOpen, setIsOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(false);
  const panelRef = useRef(null);

  // Poll unread count every 30s
  useEffect(() => {
    function pollCount() {
      api.getUnreadCount().then((d) => setUnreadCount(d.count || 0)).catch(() => {});
    }
    pollCount();
    const interval = setInterval(pollCount, 30000);
    return () => clearInterval(interval);
  }, []);

  // Load notifications when panel opens
  useEffect(() => {
    if (!isOpen) return;
    setLoading(true);
    api.getNotifications({ unread_only: false, limit: 20 })
      .then(setNotifications)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [isOpen]);

  // Close on outside click
  useEffect(() => {
    function handleClickOutside(e) {
      if (panelRef.current && !panelRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    }
    if (isOpen) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen]);

  function handleMarkRead(id) {
    api.markNotificationRead(id).then(() => {
      setNotifications((prev) => prev.map((n) => n.id === id ? { ...n, is_read: true } : n));
      setUnreadCount((c) => Math.max(0, c - 1));
    }).catch(() => {});
  }

  function handleMarkAllRead() {
    api.markAllNotificationsRead().then(() => {
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    }).catch(() => {});
  }

  return (
    <div ref={panelRef} style={{ position: "relative" }}>
      <button
        id="notification-bell-btn"
        className="notif-bell-btn"
        onClick={() => setIsOpen((o) => !o)}
        aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ""}`}
      >
        <Bell size={20} style={{ color: "var(--text-main)" }} />
        {unreadCount > 0 && (
          <motion.span 
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            className="nav-badge" 
            style={{ position: "absolute", top: -2, right: -4, background: "var(--danger-500)", color: "white", borderRadius: "10px", padding: "2px 6px", fontSize: "10px", fontWeight: "bold", border: "2px solid var(--bg-surface)" }}
          >
            {unreadCount > 99 ? "99+" : unreadCount}
          </motion.span>
        )}
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div 
            className="notif-panel card"
            initial={{ opacity: 0, y: 10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.95 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, paddingBottom: 12, borderBottom: "1px solid var(--border-color)" }}>
              <div style={{ fontWeight: 700, fontSize: 16, color: "var(--text-main)", display: "flex", alignItems: "center", gap: 8 }}>
                Notifications
                {unreadCount > 0 && (
                  <span className="badge" style={{ background: "var(--warning-100)", color: "var(--warning-700)", fontSize: 12 }}>
                    {unreadCount} unread
                  </span>
                )}
              </div>
              {unreadCount > 0 && (
                <button
                  onClick={handleMarkAllRead}
                  style={{ background: "none", border: "none", cursor: "pointer", fontSize: 13, color: "var(--primary-500)", fontWeight: 600, display: "flex", alignItems: "center", gap: 4, padding: "4px 8px", borderRadius: 4 }}
                  className="hover-bg-primary-50"
                >
                  <CheckCircle2 size={14} /> Mark all read
                </button>
              )}
            </div>

            <div className="notif-list">
              {loading && (
                <div style={{ textAlign: "center", padding: "40px 20px", color: "var(--text-muted)", fontSize: 14 }}>
                  <div className="animate-spin" style={{ display: "inline-block", marginBottom: 8 }}><Bell size={24} style={{ opacity: 0.5 }} /></div>
                  <div>Loading notifications...</div>
                </div>
              )}
              {!loading && notifications.length === 0 && (
                <div style={{ textAlign: "center", padding: "40px 20px", color: "var(--text-muted)", fontSize: 14 }}>
                  <Bell size={32} style={{ opacity: 0.3, marginBottom: 12 }} />
                  <div>You're all caught up!</div>
                </div>
              )}
              {!loading && notifications.map((n) => (
                <NotifItem key={n.id} notif={n} onRead={handleMarkRead} />
              ))}
            </div>

            {notifications.length > 0 && (
              <div style={{ textAlign: "center", paddingTop: 12, marginTop: 8, borderTop: "1px solid var(--border-color)" }}>
                <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
                  Showing last {notifications.length} notifications
                </span>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      <style>{`
        .notif-bell-btn {
          position: relative;
          background: none;
          border: none;
          cursor: pointer;
          padding: 8px;
          border-radius: 8px;
          transition: background 0.15s;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        .notif-bell-btn:hover {
          background: var(--bg-hover, rgba(0,0,0,0.05));
        }
        .notif-panel {
          position: absolute;
          right: 0;
          top: calc(100% + 8px);
          width: 380px;
          max-height: 500px;
          display: flex;
          flex-direction: column;
          background: var(--bg-surface, #fff);
          border-radius: 12px;
          box-shadow: 0 10px 40px rgba(0,0,0,0.1), 0 4px 12px rgba(0,0,0,0.05);
          border: 1px solid var(--border-color, #e5e7eb);
          z-index: 2000;
          padding: 16px;
          transform-origin: top right;
        }
        .notif-list {
          flex: 1;
          overflow-y: auto;
          display: flex;
          flex-direction: column;
          gap: 12px;
          max-height: 380px;
          padding-right: 4px;
        }
        .notif-list::-webkit-scrollbar {
          width: 6px;
        }
        .notif-list::-webkit-scrollbar-thumb {
          background: var(--border-color);
          border-radius: 4px;
        }
        .notif-item {
          padding: 14px 16px;
          border-radius: 8px;
          cursor: default;
          transition: all 0.2s;
        }
        .notif-item:hover {
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }
        .notif-read-btn {
            background: none;
            border: none;
            cursor: pointer;
            color: var(--text-muted);
            padding: 6px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s;
            flex-shrink: 0;
        }
        .notif-read-btn:hover {
            background: var(--success-50, #ecfdf5);
            color: var(--success-600, #059669);
        }
        .hover-bg-primary-50:hover {
            background: var(--primary-50, #eff6ff) !important;
        }
      `}</style>
    </div>
  );
}
