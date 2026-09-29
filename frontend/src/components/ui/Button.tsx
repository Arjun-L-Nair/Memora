import { ButtonHTMLAttributes, forwardRef } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/utils/cn";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded-xl font-medium transition-all duration-150 active:translate-y-px disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        primary: "bg-gradient-to-b from-primary-500 to-primary-600 text-primary-foreground shadow-[0_1px_0_rgba(255,255,255,0.25)_inset,0_4px_12px_rgba(15,112,121,0.28)] hover:from-primary-600 hover:to-primary-700",
        secondary: "bg-secondary-100 text-secondary-700 hover:bg-secondary-200",
        outline: "border border-border bg-surface text-foreground shadow-soft hover:border-primary-300 hover:bg-primary-50",
        ghost: "text-foreground hover:bg-primary-50",
        destructive: "bg-error text-error-foreground hover:bg-error-600",
      },
      size: {
        sm: "h-9 px-3 text-sm",
        md: "h-11 px-5 text-base",
        lg: "h-14 px-8 text-lg",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  }
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

/**
 * Standard button used across Memora.
 * Large touch-friendly target sizes; minimal, calm hover transitions.
 */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(buttonVariants({ variant, size }), className)}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";
