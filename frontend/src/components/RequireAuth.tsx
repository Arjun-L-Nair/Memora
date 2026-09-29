import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "@/contexts/AuthContext";
import type { UserRole } from "@/types";

const LOGIN_PATH: Record<UserRole, string> = {
  teacher: "/login/teacher",
  student: "/login/student",
  admin: "/login/admin",
};

/**
 * RequireAuth
 *
 * Route guard: renders children only if the currently authenticated
 * role matches `role`. Otherwise redirects to that role's login page.
 * Ownership/data-scoping is still enforced server-side (see
 * app/api/deps.py) — this is a UX guard, not the security boundary.
 */
export function RequireAuth({
  role,
  children,
}: {
  role: UserRole;
  children: React.ReactNode;
}) {
  const { role: currentRole, isAuthenticated, sessionExpired } = useAuth();
  const location = useLocation();

  if (!isAuthenticated || currentRole !== role) {
    return (
      <Navigate
        to={LOGIN_PATH[role]}
        replace
        state={{ from: location, sessionExpired }}
      />
    );
  }

  return <>{children}</>;
}
