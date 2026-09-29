import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { clearSession, getRole } from "@/services/authStorage";
import { onAuthExpired } from "@/services/authEvents";
import type { UserRole } from "@/types";

interface AuthContextValue {
  role: UserRole | null;
  isAuthenticated: boolean;
  /** True once a request's automatic token refresh has failed — i.e.
   * the previous session genuinely ended (expired/invalidated), rather
   * than the person simply never having logged in. Cleared on the next
   * successful login. */
  sessionExpired: boolean;
  /** Call after a successful login() request has already persisted tokens. */
  setRole: (role: UserRole) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

/**
 * AuthProvider
 *
 * Minimal session-state provider. It does not perform login requests
 * itself (see services/authService.ts) — it only tracks which role, if
 * any, is currently authenticated, initialized from whatever authStorage
 * already has on page load (so a browser refresh doesn't log anyone out).
 *
 * Also subscribes to authEvents.onAuthExpired (fired by apiClient.ts
 * when an automatic token refresh fails), so a session that dies
 * mid-use — e.g. an expired token, or a teacher/student deactivated by
 * an admin — is reflected here too, not just in localStorage. Once
 * `role` becomes null, RequireAuth's existing redirect-on-
 * unauthenticated logic takes over automatically.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [role, setRoleState] = useState<UserRole | null>(() => getRole());
  const [sessionExpired, setSessionExpired] = useState(false);

  useEffect(() => {
    return onAuthExpired(() => {
      setRoleState(null);
      setSessionExpired(true);
    });
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      role,
      isAuthenticated: role !== null,
      sessionExpired,
      setRole: (newRole: UserRole) => {
        setSessionExpired(false);
        setRoleState(newRole);
      },
      logout: () => {
        clearSession();
        setSessionExpired(false);
        setRoleState(null);
      },
    }),
    [role, sessionExpired]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider.");
  }
  return ctx;
}
