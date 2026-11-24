/**
 * CivicPulse Category Service
 * Provides API communication for active civic categories.
 *
 * Backend Route:
 *   GET /api/v1/categories/
 */

import { api } from "./apiClient";

let cachedCategories = null;
let cacheTime = 0;
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes memory cache

export const categoryService = {
  /**
   * Retrieve all active civic categories with managing department information.
   * Caches response for 5 minutes to avoid redundant network calls across pages.
   *
   * @param {boolean} [forceRefresh=false]
   * @returns {Promise<Array<Object>>} List of active CategoryResponse objects
   */
  getActiveCategories: async (forceRefresh = false) => {
    const now = Date.now();
    if (!forceRefresh && cachedCategories && now - cacheTime < CACHE_TTL) {
      return cachedCategories;
    }
    const res = await api.get("/categories/");
    cachedCategories = res.data || [];
    cacheTime = now;
    return cachedCategories;
  },

  /**
   * Alias for getActiveCategories for backward compatibility across components.
   *
   * @param {boolean} [forceRefresh=false]
   * @returns {Promise<Array<Object>>}
   */
  getCategories: async (forceRefresh = false) => {
    return categoryService.getActiveCategories(forceRefresh);
  },

  /**
   * Clear in-memory categories cache when updates occur.
   */
  invalidateCache: () => {
    cachedCategories = null;
    cacheTime = 0;
  },
};

export default categoryService;
