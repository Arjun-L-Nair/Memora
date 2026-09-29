/**
 * authStorage.ts
 *
 * Minimal helper around localStorage for the three token values issued
 * by the backend's auth endpoints (POST /auth/teacher/login,
 * /auth/student/login, /admin/login, /auth/refresh — see
 * app/schemas/auth.py TokenResponse). Kept as a single small module,
 * not a state-management library: this is the entire "session" concept
 * the frontend needs for now.
 *
 * `role` is stored alongside the tokens so the frontend can decide
 * which layout/routes to show without decoding the JWT client-side.
 */

import type { UserRole } from "@/types";

const ACCESS_TOKEN_KEY = "memora_access_token";
const REFRESH_TOKEN_KEY = "memora_refresh_token";
const ROLE_KEY = "memora_role";

export interface StoredSession {
  accessToken: string;
  refreshToken: string;
  role: UserRole;
}

export function saveSession(session: StoredSession): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, session.accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, session.refreshToken);
  localStorage.setItem(ROLE_KEY, session.role);
}

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function getRole(): UserRole | null {
  return localStorage.getItem(ROLE_KEY) as UserRole | null;
}

/** Updates only the access token, e.g. after a successful refresh. */
export function setAccessToken(accessToken: string): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
}

/** Updates only the refresh token (the backend rotates it on every use). */
export function setRefreshToken(refreshToken: string): void {
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
}

export function clearSession(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(ROLE_KEY);
}
