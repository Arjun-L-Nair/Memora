import { apiClient } from "@/services/apiClient";

/**
 * quizService.ts
 *
 * Wraps the student-facing /quiz-attempts endpoints (app/api/v1/quiz.py).
 * Mirrors schemas/quiz_attempt.py's response shapes.
 */

export interface QuizQuestion {
  question_id: string;
  prompt: string;
  options: string[];
}

export interface QuizAnswer {
  question_id: string;
  selected_option_index: number;
  hint_used?: boolean;
}

export interface QuizAttempt {
  id: number;
  learning_session_id: number;
  quiz_source: string;
  difficulty_level: string;
  total_questions: number;
  questions: QuizQuestion[];
  score: number | null;
  accuracy: number | null;
  time_taken_seconds: number | null;
  submitted_at: string | null;
}

export interface QuizReviewQuestion {
  question_id: string;
  prompt: string;
  options: string[];
  correct_option_index: number;
  selected_option_index: number | null;
  is_correct: boolean;
}

export interface QuizReview {
  id: number;
  score: number;
  accuracy: number;
  total_questions: number;
  questions: QuizReviewQuestion[];
}

/** Thrown when a quiz attempt already exists for this session (409). */
export class QuizAlreadyStartedError extends Error {}

/** Thrown when the session isn't in a state that allows starting a
 * quiz — e.g. it was already completed or abandoned (422). */
export class InvalidSessionStateError extends Error {}

/** Thrown when a review is requested for an attempt that hasn't been submitted yet (409). */
export class QuizNotSubmittedError extends Error {}

/**
 * Look up an already-existing quiz attempt for this session, if any,
 * without trying to create one. Returns null when the student hasn't
 * started a quiz for this session yet — that's a normal state, not an
 * error. Callers should try this first and only fall back to
 * startQuizAttempt() when it returns null, so a student revisiting a
 * quiz they already started (or already finished) can resume/see it
 * instead of hitting a dead-end 409.
 */
export async function getQuizAttemptBySession(
  learningSessionId: number
): Promise<QuizAttempt | null> {
  const { data } = await apiClient.get<QuizAttempt | null>(
    `/quiz-attempts/by-session/${learningSessionId}`
  );
  return data;
}

export async function startQuizAttempt(learningSessionId: number): Promise<QuizAttempt> {
  try {
    const { data } = await apiClient.post<QuizAttempt>(
      `/quiz-attempts/start/${learningSessionId}`
    );
    return data;
  } catch (error) {
    if (isConflict(error)) {
      throw new QuizAlreadyStartedError("A quiz attempt already exists for this session.");
    }
    if (isUnprocessable(error)) {
      throw new InvalidSessionStateError(
        "This session isn't available for a quiz right now."
      );
    }
    throw error;
  }
}

export interface HintResult {
  question_id: string;
  eliminated_option_index: number;
}

/**
 * Request an "eliminate one wrong answer" hint for a specific question.
 * The correct answer is never revealed — only one guaranteed-wrong
 * option index to grey out. Deterministic: the same question always
 * returns the same eliminated index.
 */
export async function getHint(
  quizAttemptId: number,
  questionId: string
): Promise<HintResult> {
  const { data } = await apiClient.get<HintResult>(
    `/quiz-attempts/${quizAttemptId}/hint/${questionId}`
  );
  return data;
}

export async function submitQuizAttempt(
  quizAttemptId: number,
  answers: QuizAnswer[],
  timeTakenSeconds?: number
): Promise<QuizAttempt> {
  const { data } = await apiClient.post<QuizAttempt>(`/quiz-attempts/${quizAttemptId}/submit`, {
    answers,
    time_taken_seconds: timeTakenSeconds,
  });
  return data;
}

/**
 * Full per-question review — correct answer, what the student
 * actually picked, and whether it was right — for an already-
 * submitted quiz attempt. Throws QuizNotSubmittedError (409) if
 * called before the attempt has been submitted.
 */
export async function getQuizReview(quizAttemptId: number): Promise<QuizReview> {
  try {
    const { data } = await apiClient.get<QuizReview>(`/quiz-attempts/${quizAttemptId}/review`);
    return data;
  } catch (error) {
    if (isConflict(error)) {
      throw new QuizNotSubmittedError("Quiz attempt has not been submitted yet.");
    }
    throw error;
  }
}

function isConflict(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "response" in error &&
    (error as { response?: { status?: number } }).response?.status === 409
  );
}

function isUnprocessable(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "response" in error &&
    (error as { response?: { status?: number } }).response?.status === 422
  );
}
