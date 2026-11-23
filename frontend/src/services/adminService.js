/**
 * CivicPulse Administrator Service
 * Provides API communication for municipal complaint triage, lifecycle transitions,
 * worker assignment & reassignment, workforce management, public content moderation,
 * and operational dashboard metrics.
 */

import { api } from "./apiClient";

export const adminService = {
  // ===========================================================================
  // 1. Complaint Triage & Review
  // ===========================================================================

  /**
   * Paginated search and retrieval of complaints across the municipality.
   *
   * @param {Object} [filters={}]
   * @param {string} [filters.status] Complaint status filter
   * @param {string} [filters.priority] Priority filter
   * @param {number} [filters.category_id] Category filter
   * @param {string} [filters.complaint_number] Reference number filter
   * @param {string} [filters.search] Free text search term
   * @param {number} [filters.page=1] Page number (1-based)
   * @param {number} [filters.page_size=20] Items per page
   * @param {string} [filters.sort_by="created_at"]
   * @param {string} [filters.sort_order="desc"]
   * @returns {Promise<Object>} PaginatedResponse with items in `data`
   */
  listComplaints: async (filters = {}) => {
    const params = new URLSearchParams();

    if (filters.page) params.append("page", filters.page.toString());
    if (filters.page_size) params.append("page_size", filters.page_size.toString());
    if (filters.status) params.append("status", filters.status);
    if (filters.priority) params.append("priority", filters.priority);
    if (filters.category_id) params.append("category_id", filters.category_id.toString());
    if (filters.complaint_number) params.append("complaint_number", filters.complaint_number);
    if (filters.search) params.append("search", filters.search);
    if (filters.start_date) params.append("start_date", filters.start_date);
    if (filters.end_date) params.append("end_date", filters.end_date);
    if (filters.sort_by) params.append("sort_by", filters.sort_by);
    if (filters.sort_order) params.append("sort_order", filters.sort_order);

    const queryString = params.toString();
    const endpoint = `/complaints/${queryString ? `?${queryString}` : ""}`;

    return api.getPaginated(endpoint);
  },

  /**
   * Retrieve single complaint details with location and status history.
   *
   * @param {string} complaintId UUID of complaint
   * @returns {Promise<Object>} ComplaintResponse
   */
  getComplaint: async (complaintId) => {
    const res = await api.get(`/complaints/${complaintId}`);
    return res.data;
  },

  /**
   * Triage, update category, adjust priority, or transition complaint status.
   *
   * @param {string} complaintId UUID
   * @param {Object} payload
   * @param {string} [payload.new_status] Target status (e.g. UNDER_REVIEW, REJECTED, DUPLICATE, ON_HOLD)
   * @param {number} [payload.category_id] Reclassified category ID
   * @param {string} [payload.priority] Adjusted operational priority
   * @param {string} [payload.reason] Recorded justification for adjustment/rejection/hold
   * @param {string} [payload.original_complaint_id] Referenced UUID if marking duplicate
   * @returns {Promise<Object>} Updated ComplaintResponse
   */
  reviewComplaint: async (complaintId, payload) => {
    const res = await api.patch(`/complaints/${complaintId}/review`, payload);
    return res.data;
  },

  /**
   * Execute lifecycle state transition directly.
   *
   * @param {string} complaintId UUID
   * @param {Object} payload
   * @param {string} payload.new_status Target status
   * @param {string} [payload.remarks] Transition remarks
   * @param {string} [payload.original_complaint_id]
   * @returns {Promise<Object>} Updated ComplaintResponse
   */
  transitionComplaint: async (complaintId, payload) => {
    const res = await api.post(`/complaints/${complaintId}/transitions`, payload);
    return res.data;
  },

  /**
   * Retrieve chronological audit narrative timeline for a complaint.
   *
   * @param {string} complaintId
   * @returns {Promise<Array<Object>>} List of timeline events
   */
  getComplaintTimeline: async (complaintId) => {
    const res = await api.get(`/complaints/${complaintId}/timeline`);
    return res.data;
  },

  // ===========================================================================
  // 2. Assignment & Reassignment
  // ===========================================================================

  /**
   * Assign an UNDER_REVIEW complaint to an eligible field worker.
   *
   * @param {string} complaintId UUID
   * @param {Object} payload
   * @param {string} payload.worker_id UUID of designated field worker
   * @param {string} [payload.notes] Optional dispatch remarks or special directives
   * @returns {Promise<Object>} AssignmentResponse
   */
  assignComplaint: async (complaintId, payload) => {
    const res = await api.post(`/complaints/${complaintId}/assign`, payload);
    return res.data;
  },

  /**
   * Reassign an ASSIGNED or IN_PROGRESS complaint to another eligible field worker.
   *
   * @param {string} complaintId UUID
   * @param {Object} payload
   * @param {string} payload.new_worker_id UUID of replacement technician
   * @param {string} payload.reason Mandatory justification (min 5 characters)
   * @param {string} [payload.notes] Instructions for replacement technician
   * @returns {Promise<Object>} AssignmentResponse
   */
  reassignComplaint: async (complaintId, payload) => {
    const res = await api.post(`/complaints/${complaintId}/reassign`, payload);
    return res.data;
  },

  /**
   * Retrieve assignment history for a complaint.
   *
   * @param {string} complaintId UUID
   * @returns {Promise<Array<Object>>} List of AssignmentResponse objects
   */
  getComplaintAssignments: async (complaintId) => {
    const res = await api.get(`/complaints/${complaintId}/assignments`);
    return res.data || [];
  },

  /**
   * Administrator query for all assignments across the municipality.
   *
   * @param {Object} [filters={}]
   * @param {number} [filters.department_id]
   * @param {string} [filters.worker_id]
   * @param {string} [filters.complaint_id]
   * @param {string} [filters.status]
   * @param {number} [filters.page=1]
   * @param {number} [filters.page_size=20]
   * @returns {Promise<Object>} PaginatedResponse
   */
  listAllAssignments: async (filters = {}) => {
    const params = new URLSearchParams();
    if (filters.department_id) params.append("department_id", filters.department_id.toString());
    if (filters.worker_id) params.append("worker_id", filters.worker_id);
    if (filters.complaint_id) params.append("complaint_id", filters.complaint_id);
    if (filters.status) params.append("status", filters.status);
    if (filters.page) params.append("page", filters.page.toString());
    if (filters.page_size) params.append("page_size", filters.page_size.toString());

    const queryString = params.toString();
    const endpoint = `/assignments/${queryString ? `?${queryString}` : ""}`;
    return api.getPaginated(endpoint);
  },

  /**
   * Retrieve single assignment details including complete milestone progress audit history.
   *
   * @param {string} assignmentId UUID
   * @returns {Promise<Object>} AssignmentDetailResponse
   */
  getAssignmentDetail: async (assignmentId) => {
    const res = await api.get(`/assignments/${assignmentId}`);
    return res.data;
  },

  // ===========================================================================
  // 3. Field Worker Workforce Management
  // ===========================================================================

  /**
   * List field workers across departments with optional filters.
   *
   * @param {Object} [params={}]
   * @param {number} [params.department_id]
   * @param {boolean} [params.is_available]
   * @param {string} [params.employment_status] "ACTIVE", "ON_LEAVE", "INACTIVE"
   * @param {number} [params.page=1]
   * @param {number} [params.page_size=50]
   * @returns {Promise<Object>} PaginatedResponse with items in `data`
   */
  listWorkers: async (params = {}) => {
    const query = new URLSearchParams();
    if (params.department_id) query.append("department_id", params.department_id.toString());
    if (typeof params.is_available === "boolean") query.append("is_available", params.is_available.toString());
    if (params.employment_status) query.append("employment_status", params.employment_status);
    if (params.page) query.append("page", params.page.toString());
    if (params.page_size) query.append("page_size", params.page_size.toString());

    const queryString = query.toString();
    const endpoint = `/workers/${queryString ? `?${queryString}` : ""}`;
    return api.getPaginated(endpoint);
  },

  /**
   * Retrieve single field worker profile and task metrics.
   *
   * @param {string} workerId UUID
   * @returns {Promise<Object>} WorkerResponse with active_tasks_count & completed_tasks_count
   */
  getWorker: async (workerId) => {
    const res = await api.get(`/workers/${workerId}`);
    return res.data;
  },

  /**
   * Atomically provision a new User account with FIELD_WORKER role and Worker profile.
   *
   * @param {Object} payload
   * @param {string} payload.email
   * @param {string} payload.password (8-72 chars)
   * @param {string} payload.full_name (2-100 chars)
   * @param {number} payload.department_id
   * @param {string} payload.employee_id (2-50 chars)
   * @param {string} [payload.designation]
   * @param {string} [payload.phone_number]
   * @returns {Promise<Object>} Provisioned WorkerResponse
   */
  createWorker: async (payload) => {
    const res = await api.post("/workers/", payload);
    return res.data;
  },

  /**
   * Update field worker profile attributes.
   *
   * @param {string} workerId UUID
   * @param {Object} payload Partial worker update
   * @returns {Promise<Object>} Updated WorkerResponse
   */
  updateWorker: async (workerId, payload) => {
    const res = await api.patch(`/workers/${workerId}`, payload);
    return res.data;
  },

  /**
   * Safely deactivate worker account without deleting historical assignments.
   *
   * @param {string} workerId UUID
   * @returns {Promise<Object>} Deactivated WorkerResponse
   */
  deactivateWorker: async (workerId) => {
    const res = await api.patch(`/workers/${workerId}/deactivate`);
    return res.data;
  },

  // ===========================================================================
  // 4. Public Content Moderation
  // ===========================================================================

  /**
   * Moderate complaint public visibility: publish, update, or revoke.
   *
   * @param {string} complaintId UUID
   * @param {Object} payload
   * @param {string} payload.action "PUBLISH", "UPDATE", or "REVOKE"
   * @param {string} [payload.public_title] Required for PUBLISH and UPDATE (5-200 chars)
   * @param {string} [payload.public_description] Required for PUBLISH and UPDATE (10-2000 chars)
   * @returns {Promise<Object>} ModeratePublicResponse
   */
  moderatePublic: async (complaintId, payload) => {
    const res = await api.post(`/complaints/${complaintId}/moderate-public`, payload);
    return res.data;
  },

  // ===========================================================================
  // 5. Complaint SLA Inspection (Optional Read-Only)
  // ===========================================================================

  /**
   * Inspect SLA evaluation details for a complaint if available.
   *
   * @param {string} complaintId UUID
   * @returns {Promise<Object>} SLA details
   */
  getComplaintSLA: async (complaintId) => {
    try {
      const res = await api.get(`/admin/sla/complaints/${complaintId}`);
      return res.data;
    } catch {
      return null;
    }
  },

  // ===========================================================================
  // 6. Operational Dashboard Metrics
  // ===========================================================================

  /**
   * Derive live municipal metrics for administrator dashboard using real backend queries.
   *
   * @returns {Promise<Object>} Real counts and priority queues
   */
  getDashboardMetrics: async () => {
    // Parallel queries to fetch true counts by lifecycle status
    const [
      totalRes,
      submittedRes,
      underReviewRes,
      assignedRes,
      inProgressRes,
      resolvedRes,
      closedRes,
      rejectedRes,
      recentRes,
      urgentRes,
    ] = await Promise.all([
      adminService.listComplaints({ page: 1, page_size: 1 }),
      adminService.listComplaints({ status: "SUBMITTED", page: 1, page_size: 1 }),
      adminService.listComplaints({ status: "UNDER_REVIEW", page: 1, page_size: 1 }),
      adminService.listComplaints({ status: "ASSIGNED", page: 1, page_size: 1 }),
      adminService.listComplaints({ status: "IN_PROGRESS", page: 1, page_size: 1 }),
      adminService.listComplaints({ status: "RESOLVED_AWAITING_VERIFICATION", page: 1, page_size: 1 }),
      adminService.listComplaints({ status: "CLOSED", page: 1, page_size: 1 }),
      adminService.listComplaints({ status: "REJECTED", page: 1, page_size: 1 }),
      adminService.listComplaints({ page: 1, page_size: 6, sort_by: "created_at", sort_order: "desc" }),
      adminService.listComplaints({ priority: "URGENT", page: 1, page_size: 5, sort_by: "created_at", sort_order: "desc" }),
    ]);

    return {
      total: totalRes.total_items || 0,
      submitted: submittedRes.total_items || 0,
      underReview: underReviewRes.total_items || 0,
      assigned: assignedRes.total_items || 0,
      inProgress: inProgressRes.total_items || 0,
      resolvedAwaitingVerification: resolvedRes.total_items || 0,
      closed: closedRes.total_items || 0,
      rejected: rejectedRes.total_items || 0,
      recentComplaints: recentRes.data || [],
      urgentComplaints: urgentRes.data || [],
    };
  },
};
