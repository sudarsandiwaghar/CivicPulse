/**
 * CivicPulse Authentication Service
 * Endpoints:
 *   POST /api/v1/auth/login
 *   POST /api/v1/auth/register
 *   GET  /api/v1/auth/me
 */

import { api } from "./apiClient";

export const authService = {
  login: async (credentials) => {
    const res = await api.post("/auth/login", credentials, {
      requiresAuth: false,
    });
    return res.data;
  },

  register: async (payload) => {
    const res = await api.post("/auth/register", payload, {
      requiresAuth: false,
    });
    return res.data;
  },

  getMe: async () => {
    const res = await api.get("/auth/me");
    return res.data;
  },
};
