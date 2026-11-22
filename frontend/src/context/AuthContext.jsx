/**
 * CivicPulse Authentication Context
 * Manages in-memory JWT authentication state without localStorage or sessionStorage.
 */

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { authService } from "../services/authService";
import { setTokenProvider, setUnauthorizedHandler } from "../services/apiClient";
import { AuthContext } from "./AuthContextObject";

export const AuthProvider = ({ children }) => {
  // In-memory token and user state — strictly no localStorage or sessionStorage persistence
  const [accessToken, setAccessToken] = useState(null);
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  // Expose token to API client
  useEffect(() => {
    setTokenProvider(() => accessToken);
  }, [accessToken]);

  const logout = useCallback(() => {
    setAccessToken(null);
    setUser(null);
  }, []);

  // Configure automatic logout on 401 response from backend
  useEffect(() => {
    setUnauthorizedHandler(logout);
  }, [logout]);

  const login = useCallback(async (credentials) => {
    setIsLoading(true);
    try {
      const data = await authService.login(credentials);
      setAccessToken(data.access_token);
      setUser(data.user);
      return data.user;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const register = useCallback(async (payload) => {
    setIsLoading(true);
    try {
      const newUser = await authService.register(payload);
      return newUser;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const getAccessToken = useCallback(() => accessToken, [accessToken]);

  const value = useMemo(
    () => ({
      user,
      isAuthenticated: Boolean(accessToken && user),
      isLoading,
      login,
      register,
      logout,
      getAccessToken,
    }),
    [user, accessToken, isLoading, login, register, logout, getAccessToken]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
