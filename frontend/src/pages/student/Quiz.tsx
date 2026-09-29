import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Bot, Cpu, ListChecks, Lightbulb, ArrowLeft, ArrowRight, Check } from "lucide-react";

import { AILoadingState } from "@/components/ai/AILoadingState";
import { Button } from "@/components/ui/Button";
import { useMira } from "@/contexts/MiraContext";
import {
  useSessionEngagementTracker,
  getSessionMetrics,
  recordAnswerChange,
} from "@/hooks/useSessionEngagementTracker";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import {
  InvalidSessionStateError,
  getHint,
  getQuizAttemptBySession,
  getQuizReview,
  startQuizAttempt,
  submitQuizAttempt,
  type QuizAttempt,
  type QuizReview,
} from "@/services/quizService";

// ─── Source badge ────────────────────────────────────────────────────────────
function SourceBadge({ source }: { source: string }) {
  // Backend's QuizGenerationResult.source uses "ai_generated" /
  // "template_fallback" (see app/services/quiz_providers/base.py) —
  // NOT "ollama", which is the value used by the separate reflection
  // pipeline's `generated_by` field instead. These are two different
  // fields with two different literal value sets on the backend; using
  // the wrong comparison here meant every genuinely AI-generated quiz
  // still displayed "Standard quiz" in the UI, even when Ollama had
  // succeeded exactly as intended.
  const isAI = source === "ai_generated";
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-border px-2.5 py-0.5 text-xs text-muted-foreground">
      {isAI ? <Bot className="h-3 w-3" /> : <Cpu className="h-3 w-3" />}
      {isAI ? "AI-generated" : "Standard quiz"}
    </span>
  );
}

// ─── Submitted results view ───────────────────────────────────────────────────
function QuizResults({
  attempt,
  onReflect,
}: {
  attempt: QuizAttempt;
  onReflect: () => void;
}) {
  const pct = Math.round((attempt.accuracy ?? 0) * 100);
  const [reviewing, setReviewing] = useState(false);
  const [review, setReview] = useState<QuizReview | null>(null);
  const [reviewError, setReviewError] = useState(false);

  async function toggleReview() {
    if (reviewing) {
      setReviewing(false);
      return;
    }
    setReviewing(true);
    if (review) return; // already fetched once — no need to refetch
    try {
      const data = await getQuizReview(attempt.id);
      setReview(data);
    } catch {
      setReviewError(true);
    }
  }

  return (
    <Card variant="clay">
      <CardHeader>
        <div className="flex items-start justify-between gap-4">
          <div>
            <CardTitle>Quiz Complete</CardTitle>
            <CardDescription className="mt-1">
              You scored {pct}% — {pct >= 70 ? "well done!" : "keep practising, you're improving!"}
            </CardDescription>
          </div>
          <SourceBadge source={attempt.quiz_source} />
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="rounded-lg bg-muted p-4 text-center">
          <p className="text-4xl font-bold text-foreground">{pct}%</p>
          <p className="mt-1 text-sm text-muted-foreground">
            {Math.round((attempt.accuracy ?? 0) * attempt.total_questions)} / {attempt.total_questions} correct
          </p>
        </div>

        <Button variant="outline" onClick={toggleReview}>
          {reviewing ? "Hide Answer Review" : "Review My Answers"}
        </Button>

        {reviewing && (
          <div className="flex flex-col gap-4">
            {reviewError ? (
              <p className="text-sm text-muted-foreground">Couldn't load the review right now. Please try again.</p>
            ) : review === null ? (
              <p className="text-sm text-muted-foreground">Loading review...</p>
            ) : (
              review.questions.map((q, i) => (
                <div
                  key={q.question_id}
                  className={`rounded-xl border-2 p-4 ${
                    q.is_correct ? "border-success-200 bg-success-50" : "border-error-200 bg-error-50"
                  }`}
                >
                  <p className="flex items-start gap-2 font-medium text-foreground">
                    <span
                      className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white ${
                        q.is_correct ? "bg-success-500" : "bg-error-500"
                      }`}
                    >
                      {q.is_correct ? "✓" : "✕"}
                    </span>
                    {i + 1}. {q.prompt}
                  </p>
                  <div className="mt-2 flex flex-col gap-1.5 pl-7 text-sm">
                    {q.options.map((option, optionIndex) => {
                      const isCorrectOption = optionIndex === q.correct_option_index;
                      const isSelected = optionIndex === q.selected_option_index;
                      return (
                        <div
                          key={optionIndex}
                          className={`rounded-md px-2.5 py-1 ${
                            isCorrectOption
                              ? "bg-success-100 font-medium text-success-700"
                              : isSelected
                              ? "bg-error-100 text-error-700 line-through"
                              : "text-muted-foreground"
                          }`}
                        >
                          {option}
                          {isCorrectOption && " (correct answer)"}
                          {isSelected && !isCorrectOption && " (your answer)"}
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        <Button size="lg" onClick={onReflect}>
          Continue to Reflection
        </Button>
      </CardContent>
    </Card>
  );
}

// ─── Progress dots ────────────────────────────────────────────────────────────
function QuestionProgress({
  total,
  current,
  answeredIds,
  questionIds,
}: {
  total: number;
  current: number;
  answeredIds: Set<string>;
  questionIds: string[];
}) {
  return (
    <div className="flex items-center justify-center gap-2" role="progressbar" aria-valuenow={current + 1} aria-valuemin={1} aria-valuemax={total}>
      {Array.from({ length: total }).map((_, i) => {
        const isCurrent = i === current;
        const isAnswered = answeredIds.has(questionIds[i]);
        return (
          <span
            key={i}
            className={`h-2.5 rounded-full transition-all duration-300 ${
              isCurrent
                ? "w-8 bg-primary"
                : isAnswered
                ? "w-2.5 bg-primary-300"
                : "w-2.5 bg-border"
            }`}
          />
        );
      })}
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────
export function Quiz() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const sessionId = Number(searchParams.get("session"));

  const [attempt, setAttempt] = useState<QuizAttempt | null>(null);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [currentIndex, setCurrentIndex] = useState(0);
  const [direction, setDirection] = useState<"forward" | "back">("forward");
  // Which question_ids have had their hint used, and which option
  // index was eliminated for each (so the eliminated option stays
  // struck through consistently rather than being recalculated).
  const [hintsUsed, setHintsUsed] = useState<Record<string, number>>({});
  const [invalidSessionState, setInvalidSessionState] = useState(false);
  const [error, setError] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const loadingRef = useRef(false); // prevents overlapping loadQuiz calls
  const { pushMiraEvent } = useMira();
  useSessionEngagementTracker(sessionId || null);

  // Step 1: check for an existing attempt, then start one if absent.
  // Pulled out as a standalone function (not just inline in useEffect)
  // so the "Try Again" button on a genuine failure can call the exact
  // same fetch-before-start logic again, rather than the student being
  // stuck on a dead-end error screen with no way to retry short of a
  // full page reload.
  async function loadQuiz(id: number) {
    if (loadingRef.current) return;
    loadingRef.current = true;
    setError(false);
    setInvalidSessionState(false);

    try {
      // Fetch-before-start: never blindly POST /start
      const existing = await getQuizAttemptBySession(id);
      if (existing !== null) {
        setAttempt(existing);
        return;
      }
      // No existing attempt → create one. Quiz generation may take a
      // little while (Ollama is tried first, with a template fallback
      // if it's slow or unavailable) — Mira animates playfully during
      // this wait (waiting_start/waiting_stop) instead of standing
      // idle, and the AILoadingState below covers the same wait with a
      // calm "Generating your quiz..." message as a text-based backup.
      pushMiraEvent({ type: "waiting_start" });
      try {
        const fresh = await startQuizAttempt(id);
        setAttempt(fresh);
      } finally {
        pushMiraEvent({ type: "waiting_stop" });
      }
    } catch (err) {
      if (err instanceof InvalidSessionStateError) {
        setInvalidSessionState(true);
      } else {
        setError(true);
      }
    } finally {
      loadingRef.current = false;
    }
  }

  useEffect(() => {
    if (!sessionId) { setError(true); return; }
    loadQuiz(sessionId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  useEffect(() => {
    if (attempt) setCurrentIndex(0);
  }, [attempt?.id]);

  async function handleUseHint(questionId: string) {
    if (!attempt || hintsUsed[questionId] !== undefined) return; // one hint per question
    try {
      const hint = await getHint(attempt.id, questionId);
      if (hint.eliminated_option_index >= 0) {
        setHintsUsed((prev) => ({ ...prev, [questionId]: hint.eliminated_option_index }));
        // If the student had already selected the option the hint just
        // eliminated, clear that selection so they can't submit a
        // struck-through answer.
        setAnswers((prev) => {
          if (prev[questionId] === hint.eliminated_option_index) {
            const next = { ...prev };
            delete next[questionId];
            return next;
          }
          return prev;
        });
      }
    } catch {
      // A failed hint request shouldn't block the student from taking
      // the quiz — silently no-op rather than showing an error state
      // for a non-essential assist feature.
    }
  }

  async function handleSubmit() {
    if (!attempt) return;
    setSubmitting(true);
    try {
      const answerList = attempt.questions.map((q) => ({
        question_id: q.question_id,
        selected_option_index: answers[q.question_id] ?? -1,
        hint_used: hintsUsed[q.question_id] !== undefined,
      }));
      const submitted = await submitQuizAttempt(
        attempt.id,
        answerList,
        sessionId ? getSessionMetrics(sessionId).timeSpentSeconds : undefined
      );
      setAttempt(submitted);
      pushMiraEvent({
        type: "quiz_complete",
        score: Math.round((submitted.accuracy ?? 0) * 100),
      });
    } catch {
      setError(true);
    } finally {
      setSubmitting(false);
    }
  }

  const allAnswered =
    attempt !== null &&
    attempt.questions.every((q) => answers[q.question_id] !== undefined);

  const goToReflection = () => navigate(`/student/reflection?session=${sessionId}`);

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-foreground">Quiz</h1>
        <p className="mt-1 text-muted-foreground">
          Answer each question carefully. Take your time — there's no rush.
        </p>
      </div>

      {!sessionId ? (
        <EmptyState
          icon={ListChecks}
          title="Quiz unavailable"
          description="No lesson session was found. Go back to Today's Learning and try again."
          action={<Button onClick={() => navigate("/student")}>Back to Today's Learning</Button>}
        />
      ) : error ? (
        <EmptyState
          icon={ListChecks}
          title="Couldn't load your quiz"
          description="This can happen if quiz generation took a bit long. Your progress is safe — try loading it again."
          action={
            <div className="flex gap-3">
              <Button onClick={() => loadQuiz(sessionId)}>Try Again</Button>
              <Button variant="outline" onClick={() => navigate("/student")}>
                Back to Today's Learning
              </Button>
            </div>
          }
        />
      ) : invalidSessionState ? (
        <EmptyState
          icon={ListChecks}
          title="This lesson isn't ready for a quiz"
          description="This session may have already been completed or is no longer active."
          action={<Button onClick={() => navigate("/student")}>Back to Today's Learning</Button>}
        />
      ) : attempt === null ? (
        // Still loading / starting
        <AILoadingState kind="generatingQuiz" />
      ) : attempt.submitted_at !== null ? (
        // Already submitted — show results
        <QuizResults attempt={attempt} onReflect={goToReflection} />
      ) : (
        // Active quiz — one question at a time
        (() => {
          const total = attempt.questions.length;
          const question = attempt.questions[currentIndex];
          const eliminatedIndex = hintsUsed[question.question_id];
          const hintAvailable = eliminatedIndex === undefined;
          const isAnswered = answers[question.question_id] !== undefined;
          const isLastQuestion = currentIndex === total - 1;
          const answeredIds = new Set(Object.keys(answers));
          const questionIds = attempt.questions.map((q) => q.question_id);

          function goNext() {
            if (currentIndex < total - 1) {
              setDirection("forward");
              setCurrentIndex((i) => i + 1);
            }
          }
          function goBack() {
            if (currentIndex > 0) {
              setDirection("back");
              setCurrentIndex((i) => i - 1);
            }
          }

          return (
            <Card variant="clay" className="overflow-hidden">
              <CardHeader>
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <CardTitle>Quiz</CardTitle>
                    <CardDescription>Difficulty: {attempt.difficulty_level}</CardDescription>
                  </div>
                  <SourceBadge source={attempt.quiz_source} />
                </div>
                <div className="mt-4 flex flex-col items-center gap-2">
                  <QuestionProgress
                    total={total}
                    current={currentIndex}
                    answeredIds={answeredIds}
                    questionIds={questionIds}
                  />
                  <p className="text-xs text-muted-foreground">
                    Question {currentIndex + 1} of {total}
                  </p>
                </div>
              </CardHeader>

              <CardContent className="flex flex-col gap-6">
                <div
                  key={question.question_id}
                  className={`flex flex-col gap-5 ${
                    direction === "forward" ? "animate-question-in-forward" : "animate-question-in-back"
                  }`}
                >
                  <fieldset className="flex flex-col gap-4 border-0 p-0 m-0">
                    <div className="flex items-start justify-between gap-3">
                      <legend className="text-lg font-semibold leading-snug text-foreground">
                        {question.prompt}
                      </legend>
                      <button
                        type="button"
                        onClick={() => handleUseHint(question.question_id)}
                        disabled={!hintAvailable}
                        title={hintAvailable ? "Get a hint" : "Hint already used"}
                        className={`flex shrink-0 items-center gap-1 rounded-full border px-2.5 py-1 text-xs transition-colors ${
                          hintAvailable
                            ? "border-primary-200 bg-primary-50 text-primary-700 hover:bg-primary-100"
                            : "border-border bg-muted text-muted-foreground"
                        }`}
                      >
                        <Lightbulb className="h-3 w-3" />
                        {hintAvailable ? "Hint" : "Used"}
                      </button>
                    </div>
                    <div className="flex flex-col gap-3">
                      {question.options.map((option, optionIndex) => {
                        const isEliminated = eliminatedIndex === optionIndex;
                        const isSelected = answers[question.question_id] === optionIndex;
                        return (
                          <label
                            key={optionIndex}
                            className={`flex items-center gap-3 rounded-xl border-2 p-4 text-base transition-all ${
                              isEliminated
                                ? "cursor-not-allowed border-border bg-muted opacity-50"
                                : isSelected
                                ? "cursor-pointer border-primary bg-primary-50 shadow-sm"
                                : "cursor-pointer border-border hover:border-primary-200 hover:bg-muted"
                            }`}
                          >
                            <span
                              className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 text-xs font-semibold ${
                                isSelected
                                  ? "border-primary bg-primary text-white"
                                  : "border-border text-muted-foreground"
                              }`}
                            >
                              {isSelected ? <Check className="h-3.5 w-3.5" /> : String.fromCharCode(65 + optionIndex)}
                            </span>
                            <input
                              type="radio"
                              name={question.question_id}
                              checked={isSelected}
                              disabled={isEliminated}
                              onChange={() => {
                                const alreadyAnswered =
                                  answers[question.question_id] !== undefined &&
                                  answers[question.question_id] !== optionIndex;
                                if (alreadyAnswered && sessionId) {
                                  recordAnswerChange(sessionId);
                                }
                                setAnswers((prev) => ({ ...prev, [question.question_id]: optionIndex }));
                              }}
                              className="sr-only"
                            />
                            <span className={`text-foreground ${isEliminated ? "line-through" : ""}`}>
                              {option}
                            </span>
                          </label>
                        );
                      })}
                    </div>
                  </fieldset>
                </div>

                <div className="flex items-center justify-between gap-3 border-t border-border pt-4">
                  {/*
                    Deliberately NOT right-aligning the primary action
                    (Next/Submit): Mira sits fixed in the bottom-right
                    corner of the viewport on every student page, and
                    was previously overlapping/blocking clicks on a
                    right-aligned primary button there. Put the primary
                    action on the LEFT and the secondary "Back" action
                    on the right instead — Back being harder to
                    accidentally miss-click is an acceptable trade-off
                    for Submit/Next never being obscured.
                  */}
                  {isLastQuestion ? (
                    <Button
                      size="lg"
                      disabled={!allAnswered || submitting}
                      onClick={handleSubmit}
                      className="gap-1.5"
                    >
                      {submitting ? "Submitting..." : "Submit Quiz"}
                    </Button>
                  ) : (
                    <Button size="lg" disabled={!isAnswered} onClick={goNext} className="gap-1.5">
                      Next
                      <ArrowRight className="h-4 w-4" />
                    </Button>
                  )}

                  <Button variant="outline" onClick={goBack} disabled={currentIndex === 0} className="gap-1.5">
                    <ArrowLeft className="h-4 w-4" />
                    Back
                  </Button>
                </div>

                {isLastQuestion && !allAnswered && (
                  <p className="text-center text-xs text-muted-foreground">
                    Go back and answer every question before submitting.
                  </p>
                )}
              </CardContent>
            </Card>
          );
        })()
      )}
    </div>
  );
}
