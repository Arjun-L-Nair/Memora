import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";

import {
  clearSession,
  getAccessToken,
  getRefreshToken,
  setAccessToken,
  setRefreshToken,
} from "@/services/authStorage";
import { emitAuthExpired } from "@/services/authEvents";

/**
 * Base Axios instance for Memora.
 *
 * Base URL note (Phase 16, Ticket A):
 * Backend routers mount at root (e.g. `/auth`, `/students`,
 * `/learning-plans`) — there is no `/api` prefix anywhere in the
 * FastAPI app. The default below matches that. Override via
 * VITE_API_BASE_URL in `.env` if the backend is hosted elsewhere.
 */
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  // 120s, matched to the backend's OLLAMA_TIMEOUT_SECONDS (default
  // 100s — see backend/.env.example). Quiz generation and reflection
  // generation route through Ollama server-side; on a slow/CPU-only
  // machine that budget alone can take the full 100s before falling
  // back to a template. If this client timeout were equal to or
  // shorter than the backend's Ollama budget, the frontend can abort
  // and show "failed to load" for a request that was seconds away
  // from succeeding via the fallback — wasting the backend's work and
  // showing a false failure to the student. 120s gives ~20s of
  // headroom over the backend's 100s budget for fallback generation,
  // serialization, and network overhead.
  //
  // IMPORTANT: if you change OLLAMA_TIMEOUT_SECONDS in the backend's
  // .env, raise this value to stay comfortably above it — these two
  // numbers must move together, or this exact race reappears.
  timeout: 120000,
  headers: {
    "Content-Type": "application/json",
  },
});

/**
 * A separate, bare Axios instance used ONLY for the token-refresh call
 * itself. It intentionally has none of apiClient's interceptors, so a
 * failed refresh can never trigger another refresh attempt (no
 * recursion). Kept at a short timeout since token refresh never routes
 * through Ollama or any other slow, LLM-backed endpoint.
 */
const refreshClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    "Content-Type": "application/json",
  },
});

// --- Request interceptor ---
//
// Attaches the stored access token to every outgoing request, if one
// exists. Public endpoints (login) simply won't have a token yet, so
// this is harmless to apply unconditionally.
apiClient.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// --- Response interceptor: transparent refresh-on-401 ---
//
// On a 401 (expired/invalid access token), attempt exactly one refresh
// using the stored refresh token, then retry the original request once
// with the new access token. If the refresh itself fails, the session
// is cleared (effectively logging the user out) and the original error
// is surfaced to the caller. `_retried` guards against retry loops if
// the retried request also comes back 401.
interface RetriableConfig extends InternalAxiosRequestConfig {
  _retried?: boolean;
}

let refreshInFlight: Promise<string> | null = null;

async function performRefresh(): Promise<string> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    throw new Error("No refresh token available.");
  }

  const response = await refreshClient.post("/auth/refresh", {
    refresh_token: refreshToken,
  });

  const { access_token, refresh_token } = response.data;
  setAccessToken(access_token);
  setRefreshToken(refresh_token);
  return access_token;
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalConfig = error.config as RetriableConfig | undefined;

    const isUnauthorized = error.response?.status === 401;
    const alreadyRetried = originalConfig?._retried === true;
    const isRefreshCall = originalConfig?.url === "/auth/refresh";
    // A request that never carried a bearer token in the first place
    // (e.g. a login POST) cannot be "your session expired" — there was
    // no session to expire. Excluding these prevents an ordinary wrong-
    // password login attempt from triggering a refresh attempt (and,
    // on failure, incorrectly looking like a session expiry).
    const wasAuthenticatedRequest = Boolean(
      (originalConfig?.headers as Record<string, unknown> | undefined)?.Authorization
    );

    if (
      !isUnauthorized ||
      alreadyRetried ||
      isRefreshCall ||
      !wasAuthenticatedRequest ||
      !originalConfig
    ) {
      return Promise.reject(error);
    }

    try {
      // Coalesce concurrent 401s into a single refresh call.
      refreshInFlight = refreshInFlight ?? performRefresh();
      const newAccessToken = await refreshInFlight;
      refreshInFlight = null;

      originalConfig._retried = true;
      originalConfig.headers = originalConfig.headers ?? {};
      originalConfig.headers.Authorization = `Bearer ${newAccessToken}`;
      return apiClient.request(originalConfig);
    } catch (refreshError) {
      refreshInFlight = null;
      clearSession();
      // Notify AuthContext (if mounted) that the session has genuinely
      // ended, so it can clear its state and surface this to the UI —
      // see authEvents.ts and AuthContext.tsx.
      emitAuthExpired();
      return Promise.reject(refreshError);
    }
  }
);
