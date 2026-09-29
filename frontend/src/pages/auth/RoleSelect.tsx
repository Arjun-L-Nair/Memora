import { useNavigate } from "react-router-dom";
import { GraduationCap, Users, ShieldCheck } from "lucide-react";

import { BrandMark } from "@/components/ui/BrandMark";
import { SpatialBackground } from "@/components/ui/SpatialBackground";

/**
 * RoleSelect — the app's role-selection screen (reachable via a
 * "choose a different role" link from any login page; the app's
 * actual default landing route is /login/student).
 *
 * Glassmorphism + spatial UI: a frosted panel floating above a soft
 * drifting gradient background — the adult-facing/pre-login visual
 * language used for login and teacher/admin surfaces throughout the
 * app (see globals.css's .glass-panel / .spatial-bg).
 */
export function RoleSelect() {
  const navigate = useNavigate();

  const roles = [
    {
      key: "student",
      label: "I'm a Student",
      description: "Log in with your Student ID and PIN",
      icon: GraduationCap,
      path: "/login/student",
    },
    {
      key: "teacher",
      label: "I'm a Teacher",
      description: "Manage students, plans, and analytics",
      icon: Users,
      path: "/login/teacher",
    },
    {
      key: "admin",
      label: "I'm an Administrator",
      description: "Platform oversight",
      icon: ShieldCheck,
      path: "/login/admin",
    },
  ] as const;

  const tone = {
    student: "bg-secondary-100 text-secondary-600 group-hover:bg-secondary-600",
    teacher: "bg-primary-100 text-primary-600 group-hover:bg-primary-600",
    admin: "bg-warning-100 text-warning-700 group-hover:bg-warning-600",
  } as const;

  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center gap-10 px-4 py-12">
      <SpatialBackground />

      <div className="flex flex-col items-center gap-4 text-center">
        <img src="/mira/mira-waving.webp" alt="" className="h-36 w-36 object-contain drop-shadow-[0_14px_18px_rgba(20,50,58,0.2)]" />
        <BrandMark variant="full" />
        <h1 className="mt-2 text-3xl text-foreground sm:text-4xl">How would you like to sign in?</h1>
      </div>

      <div className="grid w-full max-w-3xl gap-4 sm:grid-cols-3">
        {roles.map(({ key, label, description, icon: Icon, path }) => (
          <button
            key={key}
            onClick={() => navigate(path)}
            className="glass-panel group flex flex-col items-center gap-4 p-7 text-center transition-all duration-200 hover:-translate-y-1 hover:border-primary-200 hover:shadow-glassLg focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-secondary-300"
          >
            <span className={`flex h-16 w-16 items-center justify-center rounded-2xl shadow-soft transition-colors group-hover:text-white ${tone[key]}`}>
              <Icon className="h-8 w-8" aria-hidden="true" />
            </span>
            <span>
              <span className="block font-display text-lg font-semibold text-foreground">{label}</span>
              <span className="mt-1 block text-sm text-muted-foreground">{description}</span>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
