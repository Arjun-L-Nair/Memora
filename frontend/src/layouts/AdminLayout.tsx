import { NavLink, Outlet } from "react-router-dom";
import { LayoutDashboard, GraduationCap, Users, LogOut } from "lucide-react";
import { cn } from "@/utils/cn";
import { useAuth } from "@/contexts/AuthContext";
import { BrandMark } from "@/components/ui/BrandMark";
import { SpatialBackground } from "@/components/ui/SpatialBackground";

const navItems = [
  { label: "Dashboard", path: "/admin", icon: LayoutDashboard, end: true },
  { label: "Teachers", path: "/admin/teachers", icon: GraduationCap },
  { label: "Students", path: "/admin/students", icon: Users },
];

/**
 * Admin layout: mirrors the teacher shell's glassmorphism + spatial UI
 * treatment (deliberately, so the visual pattern matches across every
 * adult-facing surface in the app), with the same reduced navigation
 * scope as before.
 */
export function AdminLayout() {
  const { logout } = useAuth();

  return (
    <div className="relative flex min-h-screen">
      <SpatialBackground />

      <a href="#main-content" className="sr-only-focusable fixed left-4 top-4 z-50 rounded-xl bg-primary px-4 py-2 text-primary-foreground">
        Skip to content
      </a>

      <nav
        aria-label="Admin navigation"
        className="glass-panel sticky top-0 hidden h-screen w-64 flex-col rounded-none border-y-0 border-l-0 md:flex"
      >
        <div className="px-6 py-5">
          <BrandMark variant="inline" />
          <p className="mt-1 pl-12 text-xs font-medium text-muted-foreground">Admin</p>
        </div>
        <ul className="flex flex-col gap-1 px-4">
          {navItems.map(({ label, path, icon: Icon, end }) => (
            <li key={path}>
              <NavLink
                to={path}
                end={end}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium text-muted-foreground transition-colors hover:bg-primary-50 hover:text-primary-700",
                    isActive && "bg-primary-100 text-primary-700 shadow-[inset_3px_0_0_theme(colors.primary.600)] hover:bg-primary-100"
                  )
                }
              >
                <Icon className="h-5 w-5" />
                <span>{label}</span>
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      <div className="flex flex-1 flex-col">
        <header className="glass-panel sticky top-0 z-10 flex h-16 items-center rounded-none border-x-0 border-t-0 px-6">
          <BrandMark variant="inline" className="md:hidden" />
          <button
            type="button"
            onClick={logout}
            aria-label="Log out"
            className="ml-auto rounded-xl p-2.5 text-muted-foreground transition-colors hover:bg-primary-50 hover:text-primary-700"
          >
            <LogOut className="h-5 w-5" />
          </button>
        </header>
        <main id="main-content" className="flex-1 px-6 py-8 md:px-10">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
