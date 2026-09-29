import { HTMLAttributes, forwardRef } from "react";
import { cn } from "@/utils/cn";

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  /**
   * Visual treatment. "default" is the original flat card (still used
   * anywhere that hasn't opted into a themed surface).
   * "clay" — soft claymorphism for student-facing pages: puffy,
   * rounded, low-contrast dual-shadow depth.
   * "glass" — frosted glassmorphism for teacher/admin/login surfaces,
   * meant to sit above a .spatial-bg gradient background.
   */
  variant?: "default" | "clay" | "glass";
}

const VARIANT_CLASSES: Record<NonNullable<CardProps["variant"]>, string> = {
  default: "rounded-2xl border border-border/70 bg-surface p-6 shadow-soft",
  clay: "clay-card p-6",
  glass: "glass-panel p-6",
};

export const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ className, variant = "default", ...props }, ref) => (
    <div
      ref={ref}
      className={cn(VARIANT_CLASSES[variant], className)}
      {...props}
    />
  )
);
Card.displayName = "Card";

export const CardHeader = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("mb-4 flex flex-col gap-1", className)} {...props} />
  )
);
CardHeader.displayName = "CardHeader";

export const CardTitle = forwardRef<HTMLHeadingElement, HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h3 ref={ref} className={cn("text-lg font-semibold leading-snug text-foreground", className)} {...props} />
  )
);
CardTitle.displayName = "CardTitle";

export const CardDescription = forwardRef<HTMLParagraphElement, HTMLAttributes<HTMLParagraphElement>>(
  ({ className, ...props }, ref) => (
    <p ref={ref} className={cn("text-sm text-muted-foreground", className)} {...props} />
  )
);
CardDescription.displayName = "CardDescription";

export const CardContent = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("text-foreground", className)} {...props} />
  )
);
CardContent.displayName = "CardContent";
