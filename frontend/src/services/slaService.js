/**
 * CivicPulse SLA Service
 * Client for SLA policies, dual-clock monitoring, cycle history,
 * and on-demand bounded batch evaluations.
 *
 * Backend Routes:
 *   GET   /api/v1/admin/sla/policies
 *   POST  /api/v1/admin/sla/policies
 *   PATCH /api/v1/admin/sla/policies/{policy_id}
 *   POST  /api/v1/admin/sla/evaluate
 *   GET   /api/v1/admin/sla/complaints/{complaint_id}
 *   GET   /api/v1/admin/sla/complaints/{complaint_id}/history
 */

import { api } from "./apiClient";

export const slaService = {
  /**
   * Retrieve all configured SLA policies.
   *
   * @param {boolean} [activeOnly=false]
   * @returns {Promise<Array<Object>>} List of SLAPolicyResponse objects
   */
  listPolicies: async (activeOnly = false) => {
    const res = await api.get(`/admin/sla/policies${activeOnly ? "?active_only=true" : ""}`);
    return res.data || [];
  },

  /**
   * Define a new SLA policy with target response and resolution durations.
   *
   * @param {Object} payload
   * @param {string} payload.name Descriptive policy name (1-100 characters)
   * @param {string} [payload.description]
   * @param {number|null} [payload.category_id]
   * @param {string|null} [payload.priority] "LOW" | "MEDIUM" | "HIGH" | "URGENT"
   * @param {number} payload.response_time_hours Target response hours (gt 0)
   * @param {number} payload.resolution_time_hours Target resolution hours (gt 0)
   * @param {boolean} [payload.is_active=true]
   * @returns {Promise<Object>} Created SLAPolicyResponse
   */
  createPolicy: async (payload) => {
    const res = await api.post("/admin/sla/policies", payload);
    return res.data;
  },

  /**
   * Update duration targets, description, or active status of an existing SLA policy.
   *
   * @param {string} policyId UUID
   * @param {Object} payload Partial policy update
   * @returns {Promise<Object>} Updated SLAPolicyResponse
   */
  updatePolicy: async (policyId, payload) => {
    const res = await api.patch(`/admin/sla/policies/${policyId}`, payload);
    return res.data;
  },

  /**
   * Execute bounded on-demand SLA evaluation with optional filters (up to 200 complaints).
   *
   * @param {Object} [filters={}]
   * @param {string} [filters.complaint_id]
   * @param {number} [filters.department_id]
   * @param {number} [filters.category_id]
   * @param {string} [filters.priority]
   * @param {string} [filters.status]
   * @param {number} [filters.limit=50]
   * @returns {Promise<Object>} SLAEvaluationBatchResponse
   */
  evaluateBatch: async (filters = {}) => {
    const res = await api.post("/admin/sla/evaluate", filters);
    return res.data;
  },

  /**
   * Inspect live dual-clock SLA performance, deadlines, pauses, and escalation level.
   *
   * @param {string} complaintId UUID
   * @returns {Promise<Object>} ComplaintSLADetailResponse
   */
  getComplaintSLA: async (complaintId) => {
    const res = await api.get(`/admin/sla/complaints/${complaintId}`);
    return res.data;
  },

  /**
   * Retrieve immutable history records capturing performance of completed SLA cycles.
   *
   * @param {string} complaintId UUID
   * @returns {Promise<Array<Object>>} List of ComplaintSLAHistoryResponse objects
   */
  getComplaintSLAHistory: async (complaintId) => {
    const res = await api.get(`/admin/sla/complaints/${complaintId}/history`);
    return res.data || [];
  },
};
