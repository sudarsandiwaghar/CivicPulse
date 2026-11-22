/**
 * CivicPulse Notification Service
 * Client for in-app notifications, unread badges, and read state management across all user roles.
 *
 * Backend Routes:
 *   GET   /api/v1/notifications
 *   GET   /api/v1/notifications/unread-count
 *   PATCH /api/v1/notifications/{notification_id}/read
 *   POST  /api/v1/notifications/read-all
 */

import { api } from "./apiClient";

export const notificationService = {
  /**
   * Retrieve paginated notifications for the authenticated user.
   *
   * @param {Object} [params={}]
   * @param {number} [params.page=1]
   * @param {number} [params.pageSize=20]
   * @param {boolean} [params.unreadOnly=false]
   * @returns {Promise<Object>} NotificationListResponse ({ items, total, page, page_size, total_pages, unread_count })
   */
  listNotifications: async (params = {}) => {
    const { page = 1, pageSize = 20, unreadOnly = false } = params;
    const query = new URLSearchParams();
    query.append("page", String(page));
    query.append("page_size", String(pageSize));
    if (unreadOnly) {
      query.append("unread_only", "true");
    }

    const res = await api.get(`/notifications?${query.toString()}`);
    return res.data;
  },

  /**
   * Retrieve total unread notifications count for header badge.
   *
   * @returns {Promise<number>} Unread notification count
   */
  getUnreadCount: async () => {
    try {
      const res = await api.get("/notifications/unread-count");
      return res.data?.unread_count ?? 0;
    } catch {
      return 0;
    }
  },

  /**
   * Mark a specific notification as read.
   *
   * @param {string} notificationId UUID
   * @returns {Promise<Object>} Updated NotificationResponse
   */
  markAsRead: async (notificationId) => {
    const res = await api.patch(`/notifications/${notificationId}/read`);
    return res.data;
  },

  /**
   * Mark all unread notifications belonging to the authenticated user as read.
   *
   * @returns {Promise<number>} Count of marked notifications
   */
  markAllAsRead: async () => {
    const res = await api.post("/notifications/read-all");
    return res.data?.marked_read_count ?? 0;
  },
};
