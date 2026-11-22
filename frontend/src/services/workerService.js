/**
 * CivicPulse Field Worker Service
 * Provides API communication for field worker assigned tasks, acceptance,
 * work initiation, milestone progress logs, and task completion.
 *
 * Authoritative Backend Routes:
 *   GET  /api/v1/workers/me/tasks
 *   GET  /api/v1/workers/me/tasks/{assignment_id}
 *   POST /api/v1/workers/me/tasks/{assignment_id}/accept
 *   POST /api/v1/workers/me/tasks/{assignment_id}/start
 *   POST /api/v1/workers/me/tasks/{assignment_id}/progress
 *   POST /api/v1/workers/me/tasks/{assignment_id}/complete
 */

import { api } from "./apiClient";

export const workerService = {
  /**
   * Retrieve tasks assigned to the authenticated field worker with optional filtering and pagination.
   *
   * @param {Object} [params={}] Query filters
   * @param {string} [params.status] Assignment status filter (ASSIGNED, IN_PROGRESS, COMPLETED, REASSIGNED)
   * @param {string} [params.priority] Complaint priority filter (LOW, MEDIUM, HIGH, URGENT)
   * @param {number} [params.page=1] Page number (>= 1)
   * @param {number} [params.page_size=20] Items per page (1 to 100)
   * @returns {Promise<Object>} PaginatedResponse with items in `data`
   */
  getMyTasks: async (params = {}) => {
    const query = new URLSearchParams();

    if (params.status) query.append("status", params.status);
    if (params.priority) query.append("priority", params.priority);
    if (params.page) query.append("page", params.page.toString());
    if (params.page_size) query.append("page_size", params.page_size.toString());

    const queryString = query.toString();
    const endpoint = `/workers/me/tasks${queryString ? `?${queryString}` : ""}`;

    return api.getPaginated(endpoint);
  },

  /**
   * Retrieve full details of a specific assigned task with complete progress history.
   *
   * @param {string} assignmentId UUID of task assignment
   * @returns {Promise<Object>} WorkerTaskDetailResponse
   */
  getTaskDetail: async (assignmentId) => {
    const res = await api.get(`/workers/me/tasks/${assignmentId}`);
    return res.data;
  },

  /**
   * Technician acknowledges receipt of an assigned complaint task.
   *
   * @param {string} assignmentId UUID of task assignment
   * @returns {Promise<Object>} Updated WorkerTaskDetailResponse
   */
  acceptTask: async (assignmentId) => {
    const res = await api.post(`/workers/me/tasks/${assignmentId}/accept`);
    return res.data;
  },

  /**
   * Technician initiates work on site, moving assignment and complaint to IN_PROGRESS.
   *
   * @param {string} assignmentId UUID of task assignment
   * @param {string} [notes] Optional dispatch remarks passed as query parameter
   * @returns {Promise<Object>} Updated WorkerTaskDetailResponse
   */
  startTask: async (assignmentId, notes) => {
    const query = notes ? `?notes=${encodeURIComponent(notes.trim())}` : "";
    const res = await api.post(`/workers/me/tasks/${assignmentId}/start${query}`);
    return res.data;
  },

  /**
   * Record an intermediate milestone progress note or on-site observation.
   * Precondition: Assignment status must be IN_PROGRESS.
   *
   * @param {string} assignmentId UUID of task assignment
   * @param {string} description Progress description (5 - 2000 characters)
   * @returns {Promise<Object>} AssignmentProgressResponse
   */
  logProgress: async (assignmentId, description) => {
    const res = await api.post(`/workers/me/tasks/${assignmentId}/progress`, {
      description: description.trim(),
    });
    return res.data;
  },

  /**
   * Technician finishes work, moving assignment to COMPLETED and complaint to RESOLVED_AWAITING_VERIFICATION.
   * Precondition: Assignment status must be IN_PROGRESS.
   *
   * @param {string} assignmentId UUID of task assignment
   * @param {string} summary Comprehensive summary of remediation actions taken (10 - 2000 characters)
   * @returns {Promise<Object>} Updated WorkerTaskDetailResponse
   */
  completeTask: async (assignmentId, summary) => {
    const res = await api.post(`/workers/me/tasks/${assignmentId}/complete`, {
      summary: summary.trim(),
    });
    return res.data;
  },

  /**
   * Load aggregate operational metrics for worker dashboard using actual backend responses.
   *
   * @returns {Promise<Object>} Calculated metrics: { total, pendingAcceptance, inProgress, completed, recentTasks }
   */
  getDashboardMetrics: async () => {
    // 1. Fetch total assigned tasks
    const totalRes = await workerService.getMyTasks({ page: 1, page_size: 1 });
    const totalCount = totalRes.total_items || 0;

    // 2. Fetch in-progress count
    const inProgressRes = await workerService.getMyTasks({
      status: "IN_PROGRESS",
      page: 1,
      page_size: 1,
    });
    const inProgressCount = inProgressRes.total_items || 0;

    // 3. Fetch completed count
    const completedRes = await workerService.getMyTasks({
      status: "COMPLETED",
      page: 1,
      page_size: 1,
    });
    const completedCount = completedRes.total_items || 0;

    // 4. Fetch ASSIGNED tasks to partition between Pending Acceptance (!accepted_at) and Accepted
    const assignedRes = await workerService.getMyTasks({
      status: "ASSIGNED",
      page: 1,
      page_size: 100,
    });
    const assignedItems = assignedRes.data || [];
    const pendingAcceptanceCount = assignedItems.filter((t) => !t.accepted_at).length;
    const acceptedPendingStartCount = assignedItems.filter((t) => Boolean(t.accepted_at)).length;

    // 5. Fetch most recent tasks for immediate dashboard activity queue
    const recentRes = await workerService.getMyTasks({ page: 1, page_size: 5 });
    const recentTasks = recentRes.data || [];

    return {
      totalCount,
      pendingAcceptanceCount,
      acceptedPendingStartCount,
      inProgressCount,
      completedCount,
      recentTasks,
    };
  },
};
