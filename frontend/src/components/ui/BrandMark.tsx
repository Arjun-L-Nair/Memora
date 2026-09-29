/**
 * BrandMark — Memora logotype for login pages and nav headers.
 * Pure SVG + text. The mark is a soft "memory pebble" with three
 * connected nodes: connection and growth, kept quiet and rounded.
 */

interface BrandMarkProps {
  /** "full" = icon + wordmark stacked (login pages)
   *  "inline" = icon + wordmark side by side (nav) */
  variant?: "full" | "inline";
  className?: string;
}

export function BrandMark({ variant = "full", className = "" }: BrandMarkProps) {
  const size = variant === "inline" ? 34 : 52;
  const icon = (
    <svg
      viewBox="0 0 48 48"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      className="shrink-0"
      style={{ width: size, height: size }}
    >
      <defs>
        <linearGradient id="memora-mark" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#3FA3AA" />
          <stop offset="1" stopColor="#0B5A62" />
        </linearGradient>
      </defs>
      <rect x="2" y="2" width="44" height="44" rx="15" fill="url(#memora-mark)" />
      <path d="M24 15 L15 32 M24 15 L33 32 M15 32 H33" stroke="#CFEBEC" strokeWidth="2" strokeLinecap="round" fill="none" opacity="0.75" />
      <circle cx="24" cy="15" r="4.5" fill="#FFFFFF" />
      <circle cx="15" cy="32" r="4" fill="#E6E2F8" />
      <circle cx="33" cy="32" r="4" fill="#E6E2F8" />
    </svg>
  );

  if (variant === "inline") {
    return (
      <div className={`flex items-center gap-2.5 ${className}`}>
        {icon}
        <span className="font-display text-xl font-semibold leading-none tracking-tight text-primary-700">Memora</span>
      </div>
    );
  }

  return (
    <div className={`flex flex-col items-center gap-3 ${className}`}>
      {icon}
      <div className="text-center">
        <p className="font-display text-3xl font-semibold tracking-tight text-primary-700">Memora</p>
        <p className="mt-1 text-sm text-muted-foreground">Learning that adapts to you</p>
      </div>
    </div>
  );
}
