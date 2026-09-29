import { NavLink, Outlet } from "react-router-dom";
import { Home, BookOpen, ListChecks, MessageCircleHeart, TrendingUp, Puzzle, Settings as SettingsIcon, LogOut } from "lucide-react";
import { cn } from "@/utils/cn";
import { useAuth } from "@/contexts/AuthContext";
import { SensoryProvider } from "@/contexts/SensoryContext";
import { BrandMark } from "@/components/ui/BrandMark";
import { MiraWidget } from "@/components/companion/MiraWidget";

const navItems = [
  { label: "Today", path: "/student", icon: Home, end: true },
  { label: "Learning", path: "/student/learning", icon: BookOpen },
  { label: "Quiz", path: "/student/quiz", icon: ListChecks },
  { label: "Reflection", path: "/student/reflection", icon: MessageCircleHeart },
  { label: "Progress", path: "/student/progress", icon: TrendingUp },
  { label: "Skills", path: "/student/skills", icon: Puzzle },
  { label: "Settings", path: "/student/settings", icon: SettingsIcon },
];

/**
 * Student layout: extremely simple, large touch-friendly bottom/side
 * nav, minimal text, no clutter — per spec's student interface
 * principles. Visually uses claymorphism (soft, puffy, low-contrast
 * dual-shadow depth) — calmer and flatter than the glassmorphism used
 * for teacher/admin/login surfaces, deliberately, since this is the
 * surface a student spends actual learning time in.
 */
export function StudentLayout() {
  const { logout } = useAuth();

  return (
    <SensoryProvider>
      <div className="flex min-h-screen flex-col bg-gradient-to-br from-background via-white to-primary-50/60 md:flex-row">
      <a href="#main-content" className="sr-only-focusable fixed left-4 top-4 z-50 rounded-md bg-primary px-4 py-2 text-primary-foreground">
        Skip to content
      </a>

      {/* Side nav on larger screens, bottom nav on mobile */}
      <nav
        aria-label="Student navigation"
        className="clay-card sticky bottom-0 z-20 order-2 m-0 rounded-none border-x-0 border-b-0 md:top-0 md:order-1 md:h-screen md:w-64 md:shrink-0 md:rounded-none md:border-y-0 md:border-l-0"
      >
        <div className="hidden items-center justify-between px-6 py-5 md:flex">
          <div>
            <BrandMark variant="inline" />
            <p className="mt-1 pl-12 text-xs font-medium text-muted-foreground">Student</p>
          </div>
          <button
            type="button"
            onClick={logout}
            aria-label="Log out"
            className="rounded-xl p-2.5 text-muted-foreground transition-colors hover:bg-primary-50 hover:text-primary-700"
          >
            <LogOut className="h-5 w-5" />
          </button>
        </div>
        <ul className="flex justify-around p-2 md:flex-col md:justify-start md:gap-1.5 md:p-4">
          {navItems.map(({ label, path, icon: Icon, end }) => (
            <li key={path} className="flex-1 md:flex-none">
              <NavLink
                to={path}
                end={end}
                className={({ isActive }) =>
                  cn(
                    "flex flex-col items-center gap-1 rounded-xl px-2 py-2 text-xs font-medium text-muted-foreground transition-all hover:bg-primary-50 hover:text-primary-700 md:flex-row md:gap-3 md:px-4 md:py-3 md:text-sm",
                    isActive && "clay-inset text-primary-700 hover:bg-primary-50"
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

      <main id="main-content" className="order-1 flex-1 px-4 py-6 pb-48 md:order-2 mx-auto w-full max-w-5xl md:px-10 md:py-10 md:pb-64">
        <Outlet />
      </main>

      {/* Mira — persistent floating learning companion, present on all student pages */}
      <MiraWidget />
      </div>
    </SensoryProvider>
  );
}
