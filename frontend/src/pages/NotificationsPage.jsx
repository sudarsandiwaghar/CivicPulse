import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import "./DashboardPages.css";
import { notificationService } from "../services/notificationService";
import { useAuth } from "../hooks/useAuth";
import { Card, CardContent } from "../components/Card";
import { Button } from "../components/Button";
import { Spinner } from "../components/Spinner";
import { Alert } from "../components/Alert";
import { Pagination } from "../components/Pagination";
import { NotificationItem } from "../components/NotificationItem";

export const NotificationsPage = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [notifications, setNotifications] = useState([]);
  const [totalItems, setTotalItems] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [unreadCount, setUnreadCount] = useState(0);

  const [unreadOnly, setUnreadOnly] = useState(false);
  const [page, setPage] = useState(1);
  const pageSize = 15;

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [feedback, setFeedback] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);

  const fetchNotifications = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await notificationService.listNotifications({
        page,
        pageSize,
        unreadOnly,
      });

      setNotifications(res?.items || []);
      setTotalItems(res?.total || 0);
      setTotalPages(res?.total_pages || 1);
      setUnreadCount(res?.unread_count || 0);
    } catch (err) {
      setError(err.message || "Failed to load notifications.");
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize, unreadOnly]);

  useEffect(() => {
    fetchNotifications();
  }, [fetchNotifications]);

  const handleMarkRead = async (notificationId) => {
    try {
      await notificationService.markAsRead(notificationId);
      // Optimistically update item
      setNotifications((prev) =>
        prev.map((n) => (n.id === notificationId ? { ...n, is_read: true } : n))
      );
      setUnreadCount((prev) => Math.max(0, prev - 1));
    } catch {
      // Ignore background mark-read errors
    }
  };

  const handleMarkAllRead = async () => {
    if (unreadCount === 0) return;
    setActionLoading(true);
    try {
      const marked = await notificationService.markAllAsRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
      setFeedback({
        type: "success",
        message: `Marked ${marked} notification(s) as read.`,
      });
    } catch (err) {
      setFeedback({
        type: "error",
        message: err.message || "Failed to mark all notifications as read.",
      });
    } finally {
      setActionLoading(false);
    }
  };

  const handleNavigate = (targetUrl) => {
    if (targetUrl) {
      navigate(targetUrl);
    }
  };

  return (
    <div className="portal-page" style={{ maxWidth: "800px", margin: "0 auto" }}>
      {/* Page Header */}
      <div className="portal-header">
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <h1 className="portal-header-title">Notification Center</h1>
            {unreadCount > 0 && (
              <span
                style={{
                  fontSize: "0.75rem",
                  fontWeight: "700",
                  padding: "2px 8px",
                  borderRadius: "var(--radius-full)",
                  backgroundColor: "#fee2e2",
                  color: "#b91c1c",
                }}
              >
                {unreadCount} unread
              </span>
            )}
          </div>
          <p className="portal-header-subtitle">
            Real-time lifecycle events, dispatch directives, resolution updates, and SLA alerts.
          </p>
        </div>

        <div className="portal-header-actions">
          {unreadCount > 0 && (
            <Button
              variant="outline"
              size="sm"
              disabled={actionLoading}
              onClick={handleMarkAllRead}
            >
              {actionLoading ? "Updating..." : "Mark All as Read"}
            </Button>
          )}
        </div>
      </div>

      {feedback && (
        <Alert
          variant={feedback.type}
          dismissible
          onDismiss={() => setFeedback(null)}
        >
          {feedback.message}
        </Alert>
      )}

      {/* Filter Tabs */}
      <Card>
        <div
          style={{
            display: "flex",
            borderBottom: "1px solid var(--color-border-card)",
            padding: "0 1.25rem",
            gap: "1.5rem",
          }}
        >
          <button
            onClick={() => {
              if (unreadOnly) {
                setUnreadOnly(false);
                setPage(1);
              }
            }}
            style={{
              padding: "1rem 0",
              background: "none",
              border: "none",
              borderBottom: !unreadOnly ? "2px solid var(--color-primary)" : "2px solid transparent",
              color: !unreadOnly ? "var(--color-primary)" : "var(--color-text-muted)",
              fontWeight: !unreadOnly ? "600" : "500",
              fontSize: "0.875rem",
              cursor: "pointer",
            }}
          >
            All Notifications ({totalItems})
          </button>

          <button
            onClick={() => {
              if (!unreadOnly) {
                setUnreadOnly(true);
                setPage(1);
              }
            }}
            style={{
              padding: "1rem 0",
              background: "none",
              border: "none",
              borderBottom: unreadOnly ? "2px solid var(--color-primary)" : "2px solid transparent",
              color: unreadOnly ? "var(--color-primary)" : "var(--color-text-muted)",
              fontWeight: unreadOnly ? "600" : "500",
              fontSize: "0.875rem",
              cursor: "pointer",
            }}
          >
            Unread Only ({unreadCount})
          </button>
        </div>

        <CardContent>
          {isLoading ? (
            <div style={{ padding: "3rem 0", textAlign: "center" }}>
              <Spinner size="md" message="Loading notifications..." />
            </div>
          ) : error ? (
            <div style={{ padding: "1rem 0" }}>
              <Alert variant="error">{error}</Alert>
              <div style={{ marginTop: "1rem", textAlign: "center" }}>
                <Button variant="secondary" size="sm" onClick={fetchNotifications}>
                  Retry Loading
                </Button>
              </div>
            </div>
          ) : notifications.length === 0 ? (
            <div style={{ textAlign: "center", padding: "3rem 1rem", color: "var(--color-text-muted)" }}>
              <div
                style={{
                  width: 54,
                  height: 54,
                  borderRadius: "50%",
                  backgroundColor: "var(--color-bg-app)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  margin: "0 auto 1rem",
                  color: "var(--color-primary)",
                }}
              >
                <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
                  <path d="M13.73 21a2 2 0 0 1-3.46 0" />
                </svg>
              </div>
              <h3 style={{ fontSize: "1.125rem", fontWeight: "600", color: "var(--color-text-main)", marginBottom: "0.25rem" }}>
                {unreadOnly ? "No unread notifications" : "No notifications yet"}
              </h3>
              <p style={{ fontSize: "0.875rem", margin: 0, maxWidth: "380px", marginInline: "auto" }}>
                {unreadOnly
                  ? "You have acknowledged all active notifications."
                  : "You will receive in-app alerts when complaints transition or actions are required."}
              </p>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              {notifications.map((n) => (
                <NotificationItem
                  key={n.id}
                  notification={n}
                  userRole={user?.role}
                  onMarkRead={handleMarkRead}
                  onNavigate={handleNavigate}
                />
              ))}

              {totalPages > 1 && (
                <div style={{ marginTop: "1.5rem" }}>
                  <Pagination
                    currentPage={page}
                    totalPages={totalPages}
                    onPageChange={setPage}
                  />
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default NotificationsPage;
