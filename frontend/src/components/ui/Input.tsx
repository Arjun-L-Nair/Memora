import { InputHTMLAttributes, forwardRef, useId } from "react";
import { cn } from "@/utils/cn";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  helperText?: string;
  error?: string;
}

/**
 * Text input with an always-visible label for accessibility and predictability.
 */
export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, helperText, error, id, ...props }, ref) => {
    const generatedId = useId();
    const inputId = id ?? generatedId;

    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label htmlFor={inputId} className="text-sm font-medium text-foreground">
            {label}
          </label>
        )}
        <input
          id={inputId}
          ref={ref}
          aria-invalid={!!error}
          aria-describedby={helperText || error ? `${inputId}-desc` : undefined}
          className={cn(
            "h-12 w-full rounded-xl border border-border bg-surface px-4 text-base text-foreground shadow-[inset_0_1px_2px_rgba(20,50,58,0.05)] transition-colors placeholder:text-muted-foreground/70 hover:border-primary-300",
            "focus:border-primary-500 focus:outline-none focus:ring-4 focus:ring-primary-100",
            error && "border-error-500",
            className
          )}
          {...props}
        />
        {(helperText || error) && (
          <p
            id={`${inputId}-desc`}
            className={cn("text-sm", error ? "text-error-600" : "text-muted-foreground")}
          >
            {error || helperText}
          </p>
        )}
      </div>
    );
  }
);
Input.displayName = "Input";
