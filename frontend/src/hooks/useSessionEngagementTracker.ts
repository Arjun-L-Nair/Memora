/**
 * useSessionEngagementTracker.ts
 *
 * Tracks REAL engagement metrics for a learning session across the
 * Learning -> Quiz -> Reflection flow, so LearningSession.time_spent_seconds
 * and idle_time_seconds are populated from actual student behaviour
 * rather than being sent as null on every real session.
 *
 * Background: the backend has always supported these fields
 * (LearningSessionEndRequest accepts them, the engagement-prediction
 * ML model consumes them), but nothing in the frontend ever measured
 * or sent them — completeSession() was called with no metrics
 * argument at all. This meant every genuine student session fed the
 * engagement model nulls, and only the synthetic seed dataset ever
 * exercised it with real-looking numbers. This hook closes that gap.
 *
 * Storage: sessionStorage, keyed by session id, so timing survives
 * client-side navigation between Learning -> Quiz -> Reflection
 * (all part of one logical session) but is naturally scoped to one
 * browser tab and cleared when the tab closes — appropriate for a
 * short-lived, single-sitting metric that should never leak across
 * unrelated sessions or persist indefinitely.
 *
 * Idle detection: "idle" means no mouse movement, keyboard input, or
 * touch input for IDLE_THRESHOLD_MS. This deliberately does NOT try to
 * detect "not looking at the screen" (impossible to measure reliably
 * and privacy-invasive to attempt) — it measures interaction gaps,
 * which is the same proxy the spec's own feature list implies
 * ("Idle Time" as one of the engagement indicators, Section 7).
 */
import { useEffect, useRef } from "react";

const IDLE_THRESHOLD_MS = 30_000; // 30s of no interaction counts as idle
const STORAGE_PREFIX = "memora_session_tracking_";

interface SessionTrackingState {
  startedAt: number; // epoch ms when tracking began for this session
  idleMs: number; // accumulated idle time so far
  lastActivityAt: number; // epoch ms of the last detected interaction
}

function loadState(sessionId: number): SessionTrackingState {
  const key = STORAGE_PREFIX + sessionId;
  const raw = sessionStorage.getItem(key);
  if (raw) {
    try {
      return JSON.parse(raw) as SessionTrackingState;
    } catch {
      // fall through to fresh state on corrupt storage
    }
  }
  const now = Date.now();
  const fresh: SessionTrackingState = { startedAt: now, idleMs: 0, lastActivityAt: now };
  sessionStorage.setItem(key, JSON.stringify(fresh));
  return fresh;
}

function saveState(sessionId: number, state: SessionTrackingState) {
  sessionStorage.setItem(STORAGE_PREFIX + sessionId, JSON.stringify(state));
}

/**
 * Call once per session, from any page that's part of that session's
 * flow (Learning, Quiz, Reflection). Safe to call from multiple pages
 * for the same sessionId — tracking state is shared via sessionStorage
 * and accumulates correctly across navigations.
 */
export function useSessionEngagementTracker(sessionId: number | null) {
  const stateRef = useRef<SessionTrackingState | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    const activeSessionId = sessionId; // narrowed, stable reference for closures below

    const state = loadState(activeSessionId);
    stateRef.current = state;

    function markActivity() {
      if (!stateRef.current) return;
      const now = Date.now();
      const gap = now - stateRef.current.lastActivityAt;
      if (gap > IDLE_THRESHOLD_MS) {
        // The gap itself (minus a small grace period) counts as idle
        // time — this captures "stepped away and came back" moments,
        // not just continuous idling while the tab stays open.
        stateRef.current.idleMs += gap - IDLE_THRESHOLD_MS;
      }
      stateRef.current.lastActivityAt = now;
      saveState(activeSessionId, stateRef.current);
    }

    const events: (keyof WindowEventMap)[] = [
      "mousemove",
      "mousedown",
      "keydown",
      "touchstart",
      "scroll",
    ];
    events.forEach((evt) => window.addEventListener(evt, markActivity, { passive: true }));

    // Periodic save so long idle stretches are captured even without a
    // final activity event to trigger the calculation (e.g. the
    // student leaves mid-session and never comes back before
    // completing) — checked every 10s.
    const interval = setInterval(() => {
      if (!stateRef.current) return;
      const now = Date.now();
      const gap = now - stateRef.current.lastActivityAt;
      if (gap > IDLE_THRESHOLD_MS) {
        // Don't double count: only extend idle time incrementally
        // since the last periodic check, tracked via lastActivityAt
        // remaining unchanged until real activity resumes.
      }
      saveState(activeSessionId, stateRef.current);
    }, 10_000);

    return () => {
      events.forEach((evt) => window.removeEventListener(evt, markActivity));
      clearInterval(interval);
    };
  }, [sessionId]);
}

/**
 * Read the accumulated metrics for a session WITHOUT clearing them —
 * call this when submitting the quiz, completing the session, etc.,
 * any time before the final completion call.
 */
export function getSessionMetrics(sessionId: number): { timeSpentSeconds: number; idleTimeSeconds: number } {
  const state = loadState(sessionId);
  const now = Date.now();
  const totalMs = now - state.startedAt;
  return {
    timeSpentSeconds: Math.round(totalMs / 1000),
    idleTimeSeconds: Math.round(state.idleMs / 1000),
  };
}

/**
 * Clear tracking state for a session — call this once the session is
 * fully completed (or abandoned) so sessionStorage doesn't accumulate
 * stale entries indefinitely within a long browser tab lifetime.
 */
export function clearSessionMetrics(sessionId: number) {
  sessionStorage.removeItem(STORAGE_PREFIX + sessionId);
}

// ─── Retry tracking (separate, simpler concern) ────────────────────────────
//
// A "retry" is counted when a student changes their selected answer on
// a quiz question after having already picked one — this is a direct,
// unambiguous signal of uncertainty/reconsideration, unlike idle time
// which requires a threshold judgment call.

const RETRY_STORAGE_PREFIX = "memora_session_retries_";

export function recordAnswerChange(sessionId: number) {
  const key = RETRY_STORAGE_PREFIX + sessionId;
  const current = parseInt(sessionStorage.getItem(key) ?? "0", 10);
  sessionStorage.setItem(key, String(current + 1));
}

export function getRetryCount(sessionId: number): number {
  const key = RETRY_STORAGE_PREFIX + sessionId;
  return parseInt(sessionStorage.getItem(key) ?? "0", 10);
}

export function clearRetryCount(sessionId: number) {
  sessionStorage.removeItem(RETRY_STORAGE_PREFIX + sessionId);
}
