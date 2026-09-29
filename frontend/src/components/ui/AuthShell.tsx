import type { ReactNode } from "react";
import { BrandMark } from "@/components/ui/BrandMark";

type Audience = "student" | "teacher" | "admin";

const COPY: Record<Audience, { headline: string; sub: string; points: string[] }> = {
  student: {
    headline: "Ready when you are.",
    sub: "Lessons that fit the way you learn, at a pace that feels right.",
    points: ["Clear steps, calm screens", "Mira is here whenever you want help", "You choose how you learn"],
  },
  teacher: {
    headline: "See how every student learns.",
    sub: "Plan, adapt and follow progress in one place.",
    points: ["Personalised learning plans", "Progress and analytics at a glance", "Early signs when a student needs support"],
  },
  admin: {
    headline: "Keep Memora running smoothly.",
    sub: "Manage the teachers and students on the platform.",
    points: ["Add and manage teachers", "Oversee student accounts", "Platform-wide overview"],
  },
};

/** Soft node-graph motif echoing the logo, used on the brand panel. */
function NodeField() {
  return (
    <svg className="pointer-events-none absolute inset-0 h-full w-full opacity-40" viewBox="0 0 400 600" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <g stroke="#A2D8DA" strokeWidth="1.2" fill="none" opacity="0.5">
        <path d="M60 90 L170 150 L120 260 L250 300 L330 200 L170 150" />
        <path d="M250 300 L300 430 L150 500 L120 260" />
      </g>
      <g fill="#CFEBEC">
        {[[60,90,5],[170,150,7],[120,260,5],[250,300,8],[330,200,5],[300,430,6],[150,500,5]].map(([x,y,r]) => (
          <circle key={`${x}-${y}`} cx={x} cy={y} r={r} />
        ))}
      </g>
    </svg>
  );
}

/**
 * AuthShell — split-screen layout for every sign-in screen.
 * Left: a calm brand panel (Mira for students). Right: the form.
 * Purely presentational; the forms passed in keep their own logic.
 */
export function AuthShell({
  audience,
  title,
  description,
  children,
  footer,
}: {
  audience: Audience;
  title: string;
  description: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  const copy = COPY[audience];
  return (
    <div className="grid min-h-screen bg-background lg:grid-cols-[1.05fr_1fr]">
      <aside className="relative hidden overflow-hidden bg-gradient-to-br from-primary-600 via-primary-700 to-[#083E45] text-white lg:flex lg:flex-col lg:justify-between lg:p-12">
        <NodeField />
        <div className="pointer-events-none absolute -bottom-32 -right-24 h-96 w-96 rounded-full bg-secondary-400/30 blur-3xl" aria-hidden="true" />
        <div className="relative flex items-center gap-2.5">
          <svg viewBox="0 0 48 48" className="h-9 w-9" aria-hidden="true">
            <rect x="2" y="2" width="44" height="44" rx="15" fill="#fff" fillOpacity="0.16" />
            <path d="M24 15 L15 32 M24 15 L33 32 M15 32 H33" stroke="#fff" strokeOpacity="0.6" strokeWidth="2" strokeLinecap="round" fill="none" />
            <circle cx="24" cy="15" r="4.5" fill="#fff" /><circle cx="15" cy="32" r="4" fill="#E6E2F8" /><circle cx="33" cy="32" r="4" fill="#E6E2F8" />
          </svg>
          <span className="font-display text-2xl font-semibold tracking-tight">Memora</span>
        </div>

        <div className="relative max-w-md">
          {audience === "student" && (
            <div className="mb-6 flex h-56 w-56 items-center justify-center rounded-full bg-white/10 ring-1 ring-white/20">
              <img src="/mira/mira-waving.webp" alt="" className="h-52 w-52 object-contain drop-shadow-[0_18px_24px_rgba(0,0,0,0.25)]" />
            </div>
          )}
          <h2 className="font-display text-4xl font-semibold leading-tight tracking-tight">{copy.headline}</h2>
          <p className="mt-3 text-lg leading-relaxed text-primary-100">{copy.sub}</p>
          <ul className="mt-8 space-y-3 text-primary-50">
            {copy.points.map((p) => (
              <li key={p} className="flex items-center gap-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-white/15 text-xs" aria-hidden="true">✓</span>
                {p}
              </li>
            ))}
          </ul>
        </div>
        <p className="relative text-sm text-primary-200">Built for autistic learners.</p>
      </aside>

      <main className="relative flex flex-col items-center justify-center px-5 py-10 sm:px-10">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(60%_50%_at_100%_0%,rgba(173,161,229,0.18),transparent),radial-gradient(50%_40%_at_0%_100%,rgba(111,191,196,0.18),transparent)]" aria-hidden="true" />
        <div className="relative w-full max-w-md">
          <BrandMark variant="inline" className="mb-8 lg:hidden" />
          <div className="rounded-3xl border border-border/60 bg-white p-8 shadow-clayMd sm:p-10">
            <h1 className="text-3xl leading-tight text-foreground">{title}</h1>
            <p className="mt-2 text-base text-muted-foreground">{description}</p>
            <div className="mt-8">{children}</div>
          </div>
          {footer && <p className="mt-6 text-center text-sm text-muted-foreground">{footer}</p>}
        </div>
      </main>
    </div>
  );
}
