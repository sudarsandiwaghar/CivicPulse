/**
 * CivicPulse Public Complaint & Community Follower Service
 * Integrates with unauthenticated public feed endpoints and
 * authenticated citizen community following endpoints.
 */

import { api } from "./apiClient";

export const publicComplaintService = {
  /**
   * Retrieve unauthenticated public complaints feed.
   */
  getPublicFeed: async (filters = {}) => {
    const params = new URLSearchParams();

    if (filters.page) params.append("page", filters.page.toString());
    if (filters.page_size) params.append("page_size", filters.page_size.toString());
    if (filters.category_id) params.append("category_id", filters.category_id.toString());
    if (filters.status) params.append("status", filters.status);

    const queryString = params.toString();
    const endpoint = `/public/complaints${queryString ? `?${queryString}` : ""}`;

    const res = await api.get(endpoint, {
      requiresAuth: false,
    });
    return res.data;
  },

  /**
   * Retrieve unauthenticated public complaint detail.
   */
  getPublicComplaintDetail: async (complaintId) => {
    const res = await api.get(
      `/public/complaints/${complaintId}`,
      { requiresAuth: false }
    );
    return res.data;
  },

  /**
   * Authenticated citizen follows a public complaint.
   */
  followComplaint: async (complaintId) => {
    const res = await api.post(
      `/complaints/${complaintId}/follow`
    );
    return res.data;
  },

  /**
   * Authenticated citizen unfollows a public complaint.
   */
  unfollowComplaint: async (complaintId) => {
    const res = await api.delete(
      `/complaints/${complaintId}/follow`
    );
    return res.data;
  },

  /**
   * Retrieve complaints followed by the current authenticated citizen.
   */
  getFollowedComplaints: async (page = 1, pageSize = 20) => {
    const params = new URLSearchParams();
    params.append("page", page.toString());
    params.append("page_size", pageSize.toString());

    const res = await api.get(
      `/complaints/following?${params.toString()}`
    );
    return res.data;
  },
};
