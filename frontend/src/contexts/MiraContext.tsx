/**
 * MiraContext.tsx
 *
 * Pub-sub channel so Quiz.tsx and Reflection.tsx can push
 * learning-state events to the Mira widget without coupling.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  type DependencyList,
  type ReactNode,
} from "react";

// ─── Event types ──────────────────────────────────────────────────────────────
export type MiraEventType =
  | "lesson_started"
  | "quiz_correct"
  | "quiz_wrong"
  | "quiz_complete"
  | "reflection_done"
  | "waiting_start"
  | "waiting_stop";

export interface MiraEvent {
  type: MiraEventType;
  /** 0–100 score, only present on quiz_complete */
  score?: number;
}

type Listener = (event: MiraEvent) => void;

// ─── Context ──────────────────────────────────────────────────────────────────
interface MiraContextValue {
  pushMiraEvent: (event: MiraEvent) => void;
  subscribeMira: (listener: Listener) => () => void;
}

export const MiraContext = createContext<MiraContextValue | null>(null);

// ─── Provider ─────────────────────────────────────────────────────────────────
export function MiraProvider({ children }: { children: ReactNode }) {
  const listeners = useRef<Set<Listener>>(new Set());

  const pushMiraEvent = useCallback((event: MiraEvent) => {
    listeners.current.forEach((fn) => fn(event));
  }, []);

  const subscribeMira = useCallback((listener: Listener) => {
    listeners.current.add(listener);
    return () => { listeners.current.delete(listener); };
  }, []);

  return (
    <MiraContext.Provider value={{ pushMiraEvent, subscribeMira }}>
      {children}
    </MiraContext.Provider>
  );
}

// ─── Consumer hooks ───────────────────────────────────────────────────────────
/** Used by page components (Quiz, Reflection) to push events */
export function useMira() {
  const ctx = useContext(MiraContext);
  if (!ctx) throw new Error("useMira must be inside MiraProvider");
  return { pushMiraEvent: ctx.pushMiraEvent };
}

/** Used by MiraWidget to subscribe to events */
export function useMiraSubscription(
  listener: Listener,
  deps: DependencyList
) {
  const ctx = useContext(MiraContext);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const stableListener = useCallback(listener, deps);

  useEffect(() => {
    if (!ctx) return;
    return ctx.subscribeMira(stableListener);
  }, [ctx, stableListener]);
}
