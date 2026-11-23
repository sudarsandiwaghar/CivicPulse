/**
 * CivicPulse Centralized API Client
 * Built on native browser Fetch API.
 * Handles token attachment from in-memory getter and standard envelope unwrapping.
 */

import { ApiError } from "../types/api";

const rawBaseUrl =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

// Ensure no trailing slashes and guarantee /api/v1 endpoint path is appended if omitted
const cleanBaseUrl = rawBaseUrl.replace(/\/+$/, "");
const API_BASE_URL = cleanBaseUrl.endsWith("/api/v1")
  ? cleanBaseUrl
  : `${cleanBaseUrl}/api/v1`;

// In-memory token provider function (set by AuthContext)
let tokenProvider = null;
let unauthorizedHandler = null;

export const setTokenProvider = (provider) => {
  tokenProvider = provider;
};

export const setUnauthorizedHandler = (handler) => {
  unauthorizedHandler = handler;
};

export async function request(endpoint, options = {}) {
  const { requiresAuth = true, headers = {}, ...restOptions } = options;

  const url = `${API_BASE_URL}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;

  const requestHeaders = {
    "Content-Type": "application/json",
    Accept: "application/json",
    ...headers,
  };

  if (requiresAuth && tokenProvider) {
    const token = tokenProvider();
    if (token) {
      requestHeaders["Authorization"] = `Bearer ${token}`;
    }
  }

  let response;
  try {
    response = await fetch(url, {
      ...restOptions,
      headers: requestHeaders,
    });
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "Network error. Please check your connection.";
    throw new ApiError(0, message);
  }

  // Handle 401 Unauthorized
  if (response.status === 401) {
    if (unauthorizedHandler) {
      unauthorizedHandler();
    }
  }

  // Parse JSON response body
  let data;
  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    const errorData = data;
    let errorMessage = `Request failed with status ${response.status}`;
    if (errorData?.detail) {
      if (typeof errorData.detail === "string") {
        errorMessage = errorData.detail;
      } else if (Array.isArray(errorData.detail)) {
        errorMessage = errorData.detail
          .map((item) => (typeof item === "object" && item.msg ? item.msg : JSON.stringify(item)))
          .join(", ");
      } else if (typeof errorData.detail === "object") {
        errorMessage = errorData.detail.msg || JSON.stringify(errorData.detail);
      }
    } else if (errorData?.message) {
      errorMessage =
        typeof errorData.message === "string"
          ? errorData.message
          : JSON.stringify(errorData.message);
    }
    throw new ApiError(response.status, errorMessage, errorData);
  }

  return data;
}

export async function requestPaginated(endpoint, options = {}) {
  return await request(endpoint, options);
}

export const api = {
  get: (endpoint, options) =>
    request(endpoint, { ...options, method: "GET" }),

  getPaginated: (endpoint, options) =>
    requestPaginated(endpoint, { ...options, method: "GET" }),

  post: (endpoint, body, options) =>
    request(endpoint, {
      ...options,
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
    }),

  put: (endpoint, body, options) =>
    request(endpoint, {
      ...options,
      method: "PUT",
      body: body ? JSON.stringify(body) : undefined,
    }),

  patch: (endpoint, body, options) =>
    request(endpoint, {
      ...options,
      method: "PATCH",
      body: body ? JSON.stringify(body) : undefined,
    }),

  delete: (endpoint, options) =>
    request(endpoint, { ...options, method: "DELETE" }),
};
export { ApiError };
