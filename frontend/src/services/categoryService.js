/**
 * CivicPulse Category Service
 * Provides API communication for active civic categories.
 *
 * Backend Route:
 *   GET /api/v1/categories/
 */

import { api } from "./apiClient";

export const categoryService = {
  /**
   * Retrieve all active civic categories with managing department information.
   *
   * @returns {Promise<Array<Object>>} List of active CategoryResponse objects
   */
  getActiveCategories: async () => {
    const res = await api.get("/categories/");
    return res.data || [];
  },

  /**
   * Alias for getActiveCategories for backward compatibility across components.
   *
   * @returns {Promise<Array<Object>>}
   */
  getCategories: async () => {
    const res = await api.get("/categories/");
    return res.data || [];
  },
};

export default categoryService;
