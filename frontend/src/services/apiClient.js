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

// Deduplicate identical in-flight GET requests
const inFlightGetRequests = new Map();

export const setTokenProvider = (provider) => {
  tokenProvider = provider;
};

export const setUnauthorizedHandler = (handler) => {
  unauthorizedHandler = handler;
};

export async function request(endpoint, options = {}) {
  const { requiresAuth = true, headers = {}, timeout = 30000, ...restOptions } = options;

  const url = `${API_BASE_URL}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;

  // In-flight deduplication for concurrent identical GET requests
  const method = (restOptions.method || "GET").toUpperCase();
  const isGet = method === "GET";
  const authKey = requiresAuth && tokenProvider ? (tokenProvider() || "") : "";
  const dedupeKey = isGet ? `${url}:${authKey}` : null;

  if (isGet && dedupeKey && inFlightGetRequests.has(dedupeKey)) {
    return inFlightGetRequests.get(dedupeKey);
  }

  const executeRequest = async () => {
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

    // Configurable timeout to guard against hung requests and cold-start waits
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);
    const signal = restOptions.signal || controller.signal;

    let response;
    try {
      response = await fetch(url, {
        ...restOptions,
        headers: requestHeaders,
        signal,
      });
    } catch (err) {
      if (err.name === "AbortError" || err.message?.toLowerCase().includes("aborted")) {
        throw new ApiError(
          408,
          "Request timed out. The server may be waking up from sleep (Render free tier). Please retry shortly."
        );
      }
      const message =
        err instanceof Error ? err.message : "Network error. Please check your connection.";
      throw new ApiError(0, message);
    } finally {
      clearTimeout(timeoutId);
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
  };

  const promise = executeRequest();

  if (isGet && dedupeKey) {
    inFlightGetRequests.set(dedupeKey, promise);
    promise.finally(() => {
      inFlightGetRequests.delete(dedupeKey);
    });
  }

  return promise;
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
