/**
 * CivicPulse Complaint Service
 * Provides API communication for complaint creation, listing, details,
 * lifecycle state transitions, history, and unified chronological timeline.
 */

import { api } from "./apiClient";

export const complaintService = {
  /**
   * Retrieve paginated complaints filtered by citizen ownership and search criteria.
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
    if (filters.sort_by) params.append("sort_by", filters.sort_by);
    if (filters.sort_order) params.append("sort_order", filters.sort_order);

    const queryString = params.toString();
    const endpoint = `/complaints/${queryString ? `?${queryString}` : ""}`;

    return api.getPaginated(endpoint);
  },

  /**
   * Retrieve single complaint details by UUID.
   */
  getComplaint: async (complaintId) => {
    const res = await api.get(`/complaints/${complaintId}`);
    return res.data;
  },

  /**
   * Retrieve status transition audit history entries for a complaint.
   */
  getComplaintHistory: async (complaintId) => {
    const res = await api.get(`/complaints/${complaintId}/history`);
    return res.data;
  },

  /**
   * Retrieve unified chronological audit timeline for a complaint.
   */
  getComplaintTimeline: async (complaintId) => {
    const res = await api.get(`/complaints/${complaintId}/timeline`);
    return res.data;
  },

  /**
   * Submit a new civic complaint.
   */
  createComplaint: async (payload) => {
    const res = await api.post("/complaints/", payload);
    return res.data;
  },

  /**
   * Execute a permitted lifecycle transition (e.g. verify & close, reopen).
   */
  transitionStatus: async (complaintId, payload) => {
    const res = await api.post(
      `/complaints/${complaintId}/transitions`,
      payload
    );
    return res.data;
  },
};
