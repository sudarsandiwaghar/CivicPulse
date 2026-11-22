import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { notificationService } from "../services/notificationService";
import "./TopHeader.css";

export const NotificationBell = () => {
  const [unreadCount, setUnreadCount] = useState(0);
  const navigate = useNavigate();

  const fetchCount = useCallback(async () => {
    try {
      const count = await notificationService.getUnreadCount();
      setUnreadCount(count);
    } catch {
      // Graceful fallback to 0
    }
  }, []);

  useEffect(() => {
    fetchCount();

    // Re-check unread count when window gains focus
    const handleFocus = () => fetchCount();
    window.addEventListener("focus", handleFocus);
    return () => window.removeEventListener("focus", handleFocus);
  }, [fetchCount]);

  const handleClick = () => {
    navigate("/notifications");
  };

  return (
    <button
      type="button"
      className="notification-badge-btn"
      onClick={handleClick}
      title={unreadCount > 0 ? `${unreadCount} unread notifications` : "Notifications"}
      aria-label={unreadCount > 0 ? `${unreadCount} unread notifications` : "Notifications"}
    >
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
        <path d="M13.73 21a2 2 0 0 1-3.46 0" />
      </svg>

      {unreadCount > 0 && (
        <span
          style={{
            position: "absolute",
            top: "-4px",
            right: "-4px",
            minWidth: "18px",
            height: "18px",
            padding: "0 4px",
            borderRadius: "10px",
            backgroundColor: "#e11d48",
            color: "#ffffff",
            fontSize: "0.6875rem",
            fontWeight: "700",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: "0 1px 3px rgba(0,0,0,0.2)",
            lineHeight: 1,
          }}
        >
          {unreadCount > 99 ? "99+" : unreadCount}
        </span>
      )}
    </button>
  );
};

export default NotificationBell;
