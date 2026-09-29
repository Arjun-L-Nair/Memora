import { cn } from "@/utils/cn";

export interface LoadingSpinnerProps {
  size?: "sm" | "md" | "lg";
  className?: string;
  label?: string;
}

const sizeMap = {
  sm: "h-4 w-4 border-2",
  md: "h-6 w-6 border-2",
  lg: "h-10 w-10 border-[3px]",
};

/**
 * A calm, low-motion loading indicator.
 * Uses a slow, steady spin rather than bouncing or flashing effects.
 */
export function LoadingSpinner({ size = "md", className, label }: LoadingSpinnerProps) {
  return (
    <div className="flex items-center gap-3" role="status">
      <span
        className={cn(
          "inline-block animate-spin rounded-full border-primary-200 border-t-primary-600",
          sizeMap[size],
          className
        )}
        style={{ animationDuration: "900ms" }}
      />
      {label && <span className="text-sm text-muted-foreground">{label}</span>}
      <span className="sr-only">{label ?? "Loading"}</span>
    </div>
  );
}
