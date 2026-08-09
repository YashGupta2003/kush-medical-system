import { useEffect, useRef, useState } from "react";
import { api } from "../api/client.js";

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

const SEVERITY_COLORS = {
  info: { bg: "#eff6ff", border: "#bfdbfe", icon: "ℹ️", text: "#1d4ed8" },
  warning: { bg: "#fffbeb", border: "#fde68a", icon: "⚠️", text: "#92400e" },
  critical: { bg: "#fef2f2", border: "#fecaca", icon: "🚨", text: "#991b1b" },
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
  const colors = SEVERITY_COLORS[notif.severity] || SEVERITY_COLORS.info;
  const timeAgo = formatTimeAgo(notif.created_at);

  return (
    <div
      className="notif-item"
      style={{
        background: notif.is_read ? "#fff" : colors.bg,
        borderLeft: `3px solid ${notif.is_read ? "#e5e7eb" : colors.border}`,
        opacity: notif.is_read ? 0.7 : 1,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
            <span style={{ fontSize: 14 }}>{colors.icon}</span>
            <span className="badge" style={{
              background: colors.bg, color: colors.text, border: `1px solid ${colors.border}`,
              fontSize: 10, padding: "2px 6px",
            }}>
              {TYPE_LABELS[notif.notification_type] || notif.notification_type}
            </span>
            <span style={{ fontSize: 11, color: "#94a3b8" }}>{timeAgo}</span>
          </div>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#1e293b", marginTop: 4, lineHeight: 1.4 }}>
            {notif.title}
          </div>
          <div style={{ fontSize: 12, color: "#64748b", marginTop: 2, lineHeight: 1.5 }}>
            {notif.body}
          </div>
        </div>
        {!notif.is_read && (
          <button
            onClick={(e) => { e.stopPropagation(); onRead(notif.id); }}
            style={{
              background: "none", border: "none", cursor: "pointer",
              color: "#94a3b8", fontSize: 16, padding: "0 4px", flexShrink: 0,
            }}
            title="Mark as read"
          >
            ✓
          </button>
        )}
      </div>
    </div>
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
    api.markAllNotificationsRead().then((d) => {
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
        <span style={{ fontSize: 18 }}>🔔</span>
        {unreadCount > 0 && (
          <span className="nav-badge" style={{ position: "absolute", top: -4, right: -6 }}>
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="notif-panel card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <div style={{ fontWeight: 700, fontSize: 14, color: "#1e293b" }}>
              🔔 Notifications
              {unreadCount > 0 && (
                <span className="badge" style={{ marginLeft: 8, background: "#fef3c7", color: "#92400e" }}>
                  {unreadCount} unread
                </span>
              )}
            </div>
            {unreadCount > 0 && (
              <button
                onClick={handleMarkAllRead}
                style={{ background: "none", border: "none", cursor: "pointer", fontSize: 12, color: "#6366f1", fontWeight: 600 }}
              >
                Mark all read
              </button>
            )}
          </div>

          <div className="notif-list">
            {loading && (
              <div style={{ textAlign: "center", padding: 20, color: "#94a3b8", fontSize: 13 }}>
                Loading...
              </div>
            )}
            {!loading && notifications.length === 0 && (
              <div style={{ textAlign: "center", padding: 20, color: "#94a3b8", fontSize: 13 }}>
                No notifications yet
              </div>
            )}
            {!loading && notifications.map((n) => (
              <NotifItem key={n.id} notif={n} onRead={handleMarkRead} />
            ))}
          </div>

          {notifications.length > 0 && (
            <div style={{ textAlign: "center", paddingTop: 12, borderTop: "1px solid #f1f5f9" }}>
              <span style={{ fontSize: 11, color: "#94a3b8" }}>
                Showing last {notifications.length} notifications
              </span>
            </div>
          )}
        </div>
      )}

      <style>{`
        .notif-bell-btn {
          position: relative;
          background: none;
          border: none;
          cursor: pointer;
          padding: 6px 8px;
          border-radius: 8px;
          transition: background 0.15s;
          display: flex;
          align-items: center;
        }
        .notif-bell-btn:hover {
          background: rgba(99, 102, 241, 0.08);
        }
        .notif-panel {
          position: absolute;
          right: 0;
          top: calc(100% + 8px);
          width: 360px;
          max-height: 480px;
          display: flex;
          flex-direction: column;
          background: #fff;
          border-radius: 16px;
          box-shadow: 0 20px 60px rgba(0,0,0,0.15), 0 4px 16px rgba(0,0,0,0.08);
          z-index: 2000;
          padding: 16px;
          animation: notifSlideIn 0.15s ease;
        }
        @keyframes notifSlideIn {
          from { opacity: 0; transform: translateY(-8px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .notif-list {
          flex: 1;
          overflow-y: auto;
          display: flex;
          flex-direction: column;
          gap: 8px;
          max-height: 360px;
        }
        .notif-item {
          padding: 10px 12px;
          border-radius: 10px;
          cursor: default;
          transition: opacity 0.2s;
        }
      `}</style>
    </div>
  );
}
