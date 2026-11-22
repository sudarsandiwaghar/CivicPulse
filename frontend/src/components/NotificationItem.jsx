import React from "react";
import "./NotificationItem.css";

function formatTimestamp(dateStr) {
  if (!dateStr) return "";
  try {
    const d = new Date(dateStr);
    const now = new Date();
    const diffSec = Math.floor((now.getTime() - d.getTime()) / 1000);

    if (diffSec < 60) return "Just now";
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
    if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
    if (diffSec < 604800) return `${Math.floor(diffSec / 86400)}d ago`;

    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return dateStr;
  }
}

function getNotificationVisuals(type) {
  switch (type) {
    case "STATUS_CHANGE":
      return {
        bg: "#e0f2fe",
        color: "#0369a1",
        icon: (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="23 4 23 10 17 10" />
            <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
          </svg>
        ),
      };
    case "ASSIGNMENT":
      return {
        bg: "#f3e8ff",
        color: "#7e22ce",
        icon: (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
            <circle cx="9" cy="7" r="4" />
          </svg>
        ),
      };
    case "RESOLUTION_SUBMITTED":
      return {
        bg: "#dcfce7",
        color: "#15803d",
        icon: (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="20 6 9 17 4 12" />
          </svg>
        ),
      };
    case "COMPLAINT_REOPENED":
      return {
        bg: "#ffedd5",
        color: "#c2410c",
        icon: (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
            <path d="M3 3v5h5" />
            <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
            <path d="M16 16h5v5" />
          </svg>
        ),
      };
    case "SLA_WARNING":
      return {
        bg: "#fef3c7",
        color: "#b45309",
        icon: (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
        ),
      };
    case "SLA_BREACH":
      return {
        bg: "#fee2e2",
        color: "#b91c1c",
        icon: (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
        ),
      };
    case "FEEDBACK_RECEIVED":
    case "FEEDBACK_REQUEST":
      return {
        bg: "#fef9c3",
        color: "#a16207",
        icon: (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
          </svg>
        ),
      };
    case "SYSTEM":
    default:
      return {
        bg: "#f1f5f9",
        color: "#475569",
        icon: (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="16" x2="12" y2="12" />
            <line x1="12" y1="8" x2="12.01" y2="8" />
          </svg>
        ),
      };
  }
}

export const NotificationItem = ({
  notification,
  userRole,
  onMarkRead,
  onNavigate,
}) => {
  if (!notification) return null;

  const visuals = getNotificationVisuals(notification.notification_type);

  // Derive target URL
  let targetUrl = null;
  if (notification.complaint_id) {
    if (userRole === "ADMINISTRATOR") {
      targetUrl = `/admin/complaints/${notification.complaint_id}`;
    } else if (userRole === "FIELD_WORKER") {
      targetUrl = `/worker/tasks`;
    } else {
      targetUrl = `/citizen/complaints/${notification.complaint_id}`;
    }
  }

  const handleClick = () => {
    if (!notification.is_read && onMarkRead) {
      onMarkRead(notification.id);
    }
    if (targetUrl && onNavigate) {
      onNavigate(targetUrl);
    }
  };

  const handleManualMarkRead = (e) => {
    e.stopPropagation();
    if (onMarkRead) {
      onMarkRead(notification.id);
    }
  };

  return (
    <div
      className={`notification-item ${!notification.is_read ? "unread" : ""}`}
      onClick={handleClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          handleClick();
        }
      }}
    >
      <div
        className="notification-item-icon"
        style={{ backgroundColor: visuals.bg, color: visuals.color }}
      >
        {visuals.icon}
      </div>

      <div className="notification-item-content">
        <div className="notification-item-header">
          <h4 className="notification-item-title">{notification.title}</h4>
          <span className="notification-item-time">
            {formatTimestamp(notification.created_at)}
          </span>
        </div>

        <p className="notification-item-message">{notification.message}</p>

        <div className="notification-item-actions">
          {targetUrl && (
            <span className="notification-action-link">
              View Record &rarr;
            </span>
          )}

          {!notification.is_read && (
            <button
              type="button"
              className="notification-mark-read-btn"
              onClick={handleManualMarkRead}
            >
              Mark as read
            </button>
          )}
        </div>
      </div>

      {!notification.is_read && <span className="notification-unread-dot" />}
    </div>
  );
};

export default NotificationItem;
