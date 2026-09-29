import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Bot, Cpu, MessageCircleHeart, Check } from "lucide-react";

import { AILoadingState } from "@/components/ai/AILoadingState";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { completeSession } from "@/services/studentLearningService";
import { useMira } from "@/contexts/MiraContext";
import {
  useSessionEngagementTracker,
  getSessionMetrics,
  getRetryCount,
  clearSessionMetrics,
  clearRetryCount,
} from "@/hooks/useSessionEngagementTracker";
import {
  generateReflection,
  getReflectionBySession,
  type LearningReflection,
} from "@/services/reflectionService";

// ─── Source badge ─────────────────────────────────────────────────────────────
function SourceBadge({ source }: { source: string }) {
  const isAI = source === "ollama";
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-border px-2.5 py-0.5 text-xs text-muted-foreground">
      {isAI ? <Bot className="h-3 w-3" /> : <Cpu className="h-3 w-3" />}
      {isAI ? "AI-generated" : "Standard reflection"}
    </span>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────
export function Reflection() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const sessionId = Number(searchParams.get("session"));

  const [reflection, setReflection] = useState<LearningReflection | null>(null);
  const [error, setError] = useState(false);
  const [completing, setCompleting] = useState(false);
  const [completed, setCompleted] = useState(false);
  const loadingRef = useRef(false); // prevents overlapping loadReflection calls
  const { pushMiraEvent } = useMira();
  useSessionEngagementTracker(sessionId || null);

  // Fetch-before-generate: same pattern as Quiz.tsx. Pulled out as a
  // standalone function so the "Try Again" button on a genuine failure
  // can re-run it, rather than leaving the student on a dead-end error
  // screen with no way to retry short of a full page reload.
  async function loadReflection(id: number) {
    if (loadingRef.current) return;
    loadingRef.current = true;
    setError(false);

    try {
      // 1. Check whether a reflection already exists for this session
      const existing = await getReflectionBySession(id);
      if (existing !== null) {
        setReflection(existing);
        return;
      }
      // 2. None yet — generate one (Ollama first, template fallback if
      // slow or unavailable). Mira animates playfully during this wait
      // instead of standing idle; the AILoadingState below is a
      // text-based backup covering the same wait.
      pushMiraEvent({ type: "waiting_start" });
      try {
        const fresh = await generateReflection(id);
        setReflection(fresh);
      } finally {
        pushMiraEvent({ type: "waiting_stop" });
      }
    } catch {
      setError(true);
    } finally {
      loadingRef.current = false;
    }
  }

  useEffect(() => {
    if (!sessionId) { setError(true); return; }
    loadReflection(sessionId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  async function handleComplete() {
    setCompleting(true);
    try {
      // Real, measured engagement metrics — this closes the gap where
      // every genuine student session previously sent completeSession()
      // with no metrics at all, meaning time_spent_seconds,
      // idle_time_seconds, and retry_count were always null for real
      // sessions and the engagement-prediction model only ever saw
      // real-looking numbers from the synthetic seed dataset.
      const { timeSpentSeconds, idleTimeSeconds } = getSessionMetrics(sessionId);
      const retryCount = getRetryCount(sessionId);

      await completeSession(sessionId, {
        time_spent_seconds: timeSpentSeconds,
        idle_time_seconds: idleTimeSeconds,
        retry_count: retryCount,
      });

      clearSessionMetrics(sessionId);
      clearRetryCount(sessionId);

      setCompleted(true);
      pushMiraEvent({ type: "reflection_done" });
    } catch {
      setError(true);
    } finally {
      setCompleting(false);
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-3">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-secondary-50">
          <MessageCircleHeart className="h-6 w-6 text-secondary-600" aria-hidden="true" />
        </span>
        <div>
          <h1 className="text-2xl font-bold text-foreground">Reflection</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            A moment to look back on what you learned today.
          </p>
        </div>
      </div>

      {!sessionId ? (
        <EmptyState
          icon={MessageCircleHeart}
          title="Reflection unavailable"
          description="No lesson session was found. Go back to Today's Learning and try again."
          action={<Button onClick={() => navigate("/student")}>Back to Today's Learning</Button>}
        />
      ) : error ? (
        <EmptyState
          icon={MessageCircleHeart}
          title="Couldn't load your reflection"
          description="This can happen if generation took a bit long. Your quiz results are safe — try loading it again."
          action={
            <div className="flex gap-3">
              <Button onClick={() => loadReflection(sessionId)}>Try Again</Button>
              <Button variant="outline" onClick={() => navigate("/student")}>
                Back to Today's Learning
              </Button>
            </div>
          }
        />
      ) : completed ? (
        <div className="flex flex-col items-center gap-4 rounded-2xl bg-gradient-to-br from-success-50 to-primary-50 px-6 py-12 text-center">
          <span className="flex h-16 w-16 items-center justify-center rounded-full bg-success-500 text-white shadow-softMd">
            <Check className="h-8 w-8" />
          </span>
          <div>
            <h2 className="text-xl font-bold text-foreground">Session complete!</h2>
            <p className="mt-1 text-sm text-muted-foreground">Great work today. Your progress has been saved.</p>
          </div>
          <Button onClick={() => navigate("/student")}>Back to Today's Learning</Button>
        </div>
      ) : reflection === null ? (
        <AILoadingState kind="generatingReflection" />
      ) : (
        <Card variant="clay" className="bg-gradient-to-br from-secondary-50/40 to-transparent">
          <CardHeader>
            <div className="flex items-start justify-between gap-4">
              <CardTitle>Your Reflection</CardTitle>
              <SourceBadge source={reflection.generated_by} />
            </div>
          </CardHeader>
          <CardContent className="flex flex-col gap-6">
            <p className="whitespace-pre-wrap text-[16px] leading-8 text-foreground">
              {reflection.content}
            </p>
            <Button size="lg" disabled={completing} onClick={handleComplete}>
              {completing ? "Saving..." : "Complete Session"}
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
