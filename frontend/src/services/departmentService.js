/**
 * CivicPulse Department Service
 * Provides API communication for municipal department lifecycle management,
 * inspection, updates, and deactivation.
 *
 * Authoritative Backend Routes:
 *   GET    /api/v1/departments/
 *   GET    /api/v1/departments/{department_id}
 *   POST   /api/v1/departments/
 *   PATCH  /api/v1/departments/{department_id}
 *   PATCH  /api/v1/departments/{department_id}/deactivate
 *   DELETE /api/v1/departments/{department_id}
 */

import { api } from "./apiClient";

let cachedDepartments = null;
let cacheTime = 0;
const CACHE_TTL = 5 * 60 * 1000;

export const departmentService = {
  /**
   * Retrieve all registered municipal departments with optional active status filter.
   *
   * @param {boolean} [isActive] Optional filter by active status
   * @param {boolean} [forceRefresh=false]
   * @returns {Promise<Array<Object>>} List of DepartmentResponse objects
   */
  listDepartments: async (isActive, forceRefresh = false) => {
    const now = Date.now();
    if (!forceRefresh && typeof isActive !== "boolean" && cachedDepartments && now - cacheTime < CACHE_TTL) {
      return cachedDepartments;
    }
    let endpoint = "/departments/";
    if (typeof isActive === "boolean") {
      endpoint += `?is_active=${isActive}`;
    }
    const res = await api.get(endpoint);
    const data = res.data || [];
    if (typeof isActive !== "boolean") {
      cachedDepartments = data;
      cacheTime = now;
    }
    return data;
  },

  invalidateCache: () => {
    cachedDepartments = null;
    cacheTime = 0;
  },

  /**
   * Retrieve details for a single department by ID.
   *
   * @param {number} departmentId
   * @returns {Promise<Object>} DepartmentResponse with categories_count & workers_count
   */
  getDepartment: async (departmentId) => {
    const res = await api.get(`/departments/${departmentId}`);
    return res.data;
  },

  /**
   * Register a new municipal department with unique code and name.
   *
   * @param {Object} payload
   * @param {string} payload.name Department name (2-100 characters)
   * @param {string} payload.code Unique uppercase code (2-20 characters)
   * @param {string} [payload.description]
   * @param {string} [payload.contact_email]
   * @param {string} [payload.contact_phone]
   * @param {boolean} [payload.is_active=true]
   * @returns {Promise<Object>} DepartmentResponse
   */
  createDepartment: async (payload) => {
    const res = await api.post("/departments/", payload);
    departmentService.invalidateCache();
    return res.data;
  },

  /**
   * Update department details.
   *
   * @param {number} departmentId
   * @param {Object} payload Partial department update
   * @returns {Promise<Object>} Updated DepartmentResponse
   */
  updateDepartment: async (departmentId, payload) => {
    const res = await api.patch(`/departments/${departmentId}`, payload);
    departmentService.invalidateCache();
    return res.data;
  },

  /**
   * Safely deactivate a department without deleting records.
   *
   * @param {number} departmentId
   * @returns {Promise<Object>} Updated DepartmentResponse
   */
  deactivateDepartment: async (departmentId) => {
    const res = await api.patch(`/departments/${departmentId}/deactivate`);
    departmentService.invalidateCache();
    return res.data;
  },
};
