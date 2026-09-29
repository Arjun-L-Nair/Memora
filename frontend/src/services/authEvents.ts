/**
 * authEvents.ts
 *
 * apiClient.ts's response interceptor runs outside the React tree, so
 * it has no direct way to update AuthContext's state when a session
 * genuinely dies (refresh attempt fails). This tiny pub-sub bridges
 * the two: the interceptor calls emitAuthExpired(), and AuthContext
 * subscribes once on mount to react to it (clear its state, surface a
 * "session expired" indication, and let RequireAuth's existing
 * redirect-on-unauthenticated logic take it from there).
 *
 * Deliberately not a general-purpose event bus — one event, one
 * purpose, kept small on purpose.
 */

type Listener = () => void;

const listeners = new Set<Listener>();

export function onAuthExpired(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function emitAuthExpired(): void {
  listeners.forEach((listener) => listener());
}
