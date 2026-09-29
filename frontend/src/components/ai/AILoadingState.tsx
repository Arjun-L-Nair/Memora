import { useEffect, useState } from "react";
import { Sparkles } from "lucide-react";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { cn } from "@/utils/cn";

export type AILoadingKind =
  | "preparingLesson"
  | "generatingQuiz"
  | "analyzingLearning"
  | "generatingReflection";

const MESSAGES: Record<AILoadingKind, string> = {
  preparingLesson: "Preparing Lesson...",
  generatingQuiz: "Generating Quiz...",
  analyzingLearning: "Analyzing Learning...",
  generatingReflection: "Generating Reflection...",
};

export interface AILoadingStateProps {
  kind: AILoadingKind;
  className?: string;
}

/**
 * Calm, predictable loading indicator shown during AI operations
 * (engagement prediction, quiz generation, reflection generation).
 *
 * Per spec: no excessive motion, no distracting animation — a single
 * steady spinner plus a static, clear status message.
 *
 * Quiz/reflection generation specifically can take a while on
 * CPU-only hardware (Ollama is tried first, with a generous timeout
 * before falling back to a template — see backend OLLAMA_TIMEOUT_SECONDS).
 * A silent wait beyond a few seconds reads as broken, which is
 * especially unsettling for an autistic learner who relies on
 * predictability. A single calm reassurance line appears after 8
 * seconds — not a countdown or percentage (which would need to be
 * accurate to be trustworthy), just confirmation that the wait is
 * expected and normal.
 */
export function AILoadingState({ kind, className }: AILoadingStateProps) {
  const [showReassurance, setShowReassurance] = useState(false);

  useEffect(() => {
    setShowReassurance(false);
    const timer = setTimeout(() => setShowReassurance(true), 8000);
    return () => clearTimeout(timer);
  }, [kind]);

  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-2xl border border-primary-100 bg-gradient-to-b from-primary-50/70 to-surface px-6 py-12 text-center shadow-soft",
        className
      )}
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary-100">
        <Sparkles className="h-5 w-5 text-primary-600" />
      </div>
      <LoadingSpinner size="sm" />
      <p className="text-sm font-medium text-foreground">{MESSAGES[kind]}</p>
      {showReassurance && (
        <p className="max-w-xs text-xs text-muted-foreground">
          This can take a little while. No need to refresh — it's still working.
        </p>
      )}
    </div>
  );
}
