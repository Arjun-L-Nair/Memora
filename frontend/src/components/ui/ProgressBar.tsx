import { cn } from "@/utils/cn";

export interface ProgressBarProps {
  value: number; // 0-100
  label?: string;
  className?: string;
}

/**
 * Simple horizontal progress bar. No animation beyond a smooth width
 * transition, in line with the platform's low-sensory-overload principle.
 */
export function ProgressBar({ value, label, className }: ProgressBarProps) {
  const clamped = Math.max(0, Math.min(100, value));

  return (
    <div className={cn("w-full", className)}>
      {label && (
        <div className="mb-1.5 flex justify-between text-sm">
          <span className="text-foreground">{label}</span>
          <span className="text-muted-foreground">{clamped}%</span>
        </div>
      )}
      <div
        role="progressbar"
        aria-valuenow={clamped}
        aria-valuemin={0}
        aria-valuemax={100}
        className="h-3 w-full overflow-hidden rounded-full bg-primary-100/70 shadow-[inset_0_1px_2px_rgba(20,50,58,0.08)]"
      >
        <div
          className="h-full rounded-full bg-gradient-to-r from-primary-400 to-primary-600 transition-[width] duration-500 ease-out"
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  );
}
