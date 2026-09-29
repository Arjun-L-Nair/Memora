import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { getSensoryProfile, updateSensoryProfile, type SensoryProfile } from "@/services/sensoryProfileService";

interface SensoryContextValue {
  profile: SensoryProfile | null;
  /** Loading is only true on first fetch — after that `profile` is
   * never null again for the lifetime of a student session, so pages
   * that read this context don't need their own loading branch just
   * to use sensory settings. */
  loading: boolean;
  /** True if the initial fetch failed. Distinct from `loading`
   * because "not loading and profile is null" is otherwise
   * ambiguous — a page that only checked `loading` couldn't tell a
   * genuine failure apart from "still loading" and would show a
   * spinner forever instead of a real error. */
  error: boolean;
  /** Convenience wrapper around sensoryProfileService.updateSensoryProfile
   * that also updates local context state, so a change (e.g. from the
   * Settings page) is reflected everywhere immediately without a
   * second fetch. */
  update: (patch: Partial<SensoryProfile>) => Promise<void>;
}

const SensoryContext = createContext<SensoryContextValue | undefined>(undefined);

/**
 * SensoryProvider
 *
 * Fetches the authenticated student's SensoryProfile once and makes it
 * available app-wide, AND is the single place that actually applies it
 * to the page: reduce_motion / high_contrast / font_preference are
 * translated into CSS classes on <html> here, so every page and every
 * existing animation/transition in the app is affected without each
 * component needing its own sensory-aware logic. mute_sounds and
 * preferred_mode are exposed via context for components that play
 * audio or choose a content-presentation mode (see the "Listen to
 * this lesson" control on the Learning page) to read directly.
 *
 * Mounted once, in StudentLayout only — sensory preferences are a
 * student-facing concept; teacher/admin surfaces are unaffected.
 */
export function SensoryProvider({ children }: { children: ReactNode }) {
  const [profile, setProfile] = useState<SensoryProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getSensoryProfile()
      .then((data) => { if (!cancelled) setProfile(data); })
      .catch(() => { if (!cancelled) setError(true); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  // Apply reduce_motion / high_contrast / font_preference to <html> as
  // classes. Keeping this as classes (rather than inline styles)
  // means the actual visual rules live in one place — globals.css —
  // and can be reviewed/adjusted without touching this file.
  useEffect(() => {
    const root = document.documentElement;

    root.classList.toggle("reduce-motion", Boolean(profile?.reduce_motion));
    root.classList.toggle("high-contrast", Boolean(profile?.high_contrast));
    root.classList.toggle("font-opendyslexic", profile?.font_preference === "opendyslexic");

    return () => {
      root.classList.remove("reduce-motion", "high-contrast", "font-opendyslexic");
    };
  }, [profile?.reduce_motion, profile?.high_contrast, profile?.font_preference]);

  async function update(patch: Partial<SensoryProfile>) {
    const updated = await updateSensoryProfile(patch);
    setProfile(updated);
  }

  return (
    <SensoryContext.Provider value={{ profile, loading, error, update }}>
      {children}
    </SensoryContext.Provider>
  );
}

export function useSensory(): SensoryContextValue {
  const ctx = useContext(SensoryContext);
  if (!ctx) {
    throw new Error("useSensory must be used within a SensoryProvider");
  }
  return ctx;
}
