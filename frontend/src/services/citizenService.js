/**
 * CivicPulse Citizen Service
 * Provides API communication for citizen personal reporting features.
 */

import { api } from "./apiClient";

export const citizenService = {
  getDashboard: async () => {
    const res = await api.get("/citizens/me/dashboard");
    return res.data;
  },
};
