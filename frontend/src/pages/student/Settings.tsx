/**
 * pages/student/Settings.tsx
 *
 * Sensory Profile settings — lets a student (or a caregiver helping
 * them) adjust sensory/cognitive-load preferences that the rest of
 * Memora reads (reduced motion, high contrast, muted sounds, font,
 * preferred input mode, sensory sensitivity, attention span).
 *
 * Changes save via PUT /sensory-profile (partial update) with a
 * short "Saved" confirmation, and a Reset-to-defaults action.
 */
import { useState } from "react";
import { Save, RotateCcw, Eye, Ear, Type, Layers } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { cn } from "@/utils/cn";
import { useSensory } from "@/contexts/SensoryContext";
import type { SensoryProfile } from "@/services/sensoryProfileService";

const DEFAULTS: Omit<SensoryProfile, "student_id"> = {
  preferred_mode: "mixed",
  sensory_sensitivity_score: 0.5,
  reduce_motion: false,
  high_contrast: false,
  mute_sounds: false,
  font_preference: "default",
  attention_span_minutes: 15,
};

const MODE_OPTIONS: { value: SensoryProfile["preferred_mode"]; label: string; icon: typeof Eye }[] = [
  { value: "visual", label: "Visual", icon: Eye },
  { value: "auditory", label: "Auditory", icon: Ear },
  { value: "text", label: "Text", icon: Type },
  { value: "mixed", label: "Mixed", icon: Layers },
];

function ToggleRow({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (next: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-4 py-3">
      <div>
        <p className="text-sm font-medium text-foreground">{label}</p>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
      <button
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative inline-flex h-6 w-11 shrink-0 rounded-full transition-colors",
          checked ? "bg-primary" : "bg-border",
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform",
            checked ? "translate-x-5" : "translate-x-0.5",
          )}
        />
      </button>
    </div>
  );
}

export function Settings() {
  // Sourced from the shared SensoryProvider (mounted once in
  // StudentLayout) rather than fetching its own copy — this is what
  // makes a change here take effect app-wide immediately (reduce
  // motion, high contrast, font) without needing a page reload,
  // since every page reads the same context instance.
  const { profile, loading, error: fetchError, update } = useSensory();
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [saveError, setSaveError] = useState(false);

  async function save(patch: Partial<SensoryProfile>) {
    setSaving(true);
    try {
      await update(patch);
      setSavedAt(Date.now());
    } catch {
      setSaveError(true);
    } finally {
      setSaving(false);
    }
  }

  if (fetchError) {
    return (
      <Card variant="clay">
        <CardContent className="py-8 text-center text-sm text-muted-foreground">
          Couldn't load your settings right now. Please try again in a moment.
        </CardContent>
      </Card>
    );
  }

  if (loading || !profile) {
    return (
      <div className="flex justify-center py-12">
        <LoadingSpinner />
      </div>
    );
  }

  return (
    <SettingsForm profile={profile} save={save} saving={saving} savedAt={savedAt} saveError={saveError} />
  );
}

/**
 * Split into its own component purely so the two range sliders can
 * hold local "drag preview" state (draftSensitivity/draftAttention)
 * without that state needing to live in the shared SensoryContext —
 * context holds only the last SAVED value; the slider's live position
 * while dragging is this component's own concern, committed via
 * save() on release.
 */
function SettingsForm({
  profile,
  save,
  saving,
  savedAt,
  saveError,
}: {
  profile: SensoryProfile;
  save: (patch: Partial<SensoryProfile>) => Promise<void>;
  saving: boolean;
  savedAt: number | null;
  saveError: boolean;
}) {
  const [draftSensitivity, setDraftSensitivity] = useState(profile.sensory_sensitivity_score);
  const [draftAttention, setDraftAttention] = useState(profile.attention_span_minutes);

  // Defined here (not in the parent Settings component) because
  // resetting to defaults needs to update the local slider draft
  // state too, not just trigger a save — otherwise the sliders would
  // keep showing their pre-reset drag position until the next drag,
  // even though the underlying saved value had already changed.
  async function resetToDefaults() {
    setDraftSensitivity(DEFAULTS.sensory_sensitivity_score);
    setDraftAttention(DEFAULTS.attention_span_minutes);
    await save(DEFAULTS);
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Sensory Settings</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          These settings help Memora feel comfortable for you. Change anything, anytime.
        </p>
      </div>

      <Card variant="clay">
        <CardHeader>
          <CardTitle>Preferred way to learn</CardTitle>
          <CardDescription>How you'd like content shown to you most of the time.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {MODE_OPTIONS.map(({ value, label, icon: Icon }) => (
              <button
                key={value}
                onClick={() => save({ preferred_mode: value })}
                aria-pressed={profile.preferred_mode === value}
                className={cn(
                  "flex flex-col items-center gap-2 rounded-xl border p-4 text-sm font-medium transition-colors",
                  profile.preferred_mode === value
                    ? "border-primary bg-primary-50 text-primary-700"
                    : "border-border bg-background text-foreground hover:bg-muted",
                )}
              >
                <Icon className="h-5 w-5" />
                {label}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card variant="clay">
        <CardHeader>
          <CardTitle>Sensory sensitivity</CardTitle>
          <CardDescription>
            Higher sensitivity means Memora will be more careful about motion, sound, and difficulty increases.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={draftSensitivity}
            onChange={(e) => setDraftSensitivity(Number(e.target.value))}
            onMouseUp={(e) => save({ sensory_sensitivity_score: Number((e.target as HTMLInputElement).value) })}
            onTouchEnd={(e) => save({ sensory_sensitivity_score: Number((e.target as HTMLInputElement).value) })}
            className="w-full accent-primary"
            aria-label="Sensory sensitivity"
          />
          <div className="mt-1 flex justify-between text-xs text-muted-foreground">
            <span>Low</span>
            <span>{Math.round(draftSensitivity * 100)}%</span>
            <span>High</span>
          </div>
        </CardContent>
      </Card>

      <Card variant="clay">
        <CardHeader>
          <CardTitle>Display &amp; sound</CardTitle>
        </CardHeader>
        <CardContent className="divide-y divide-border">
          <ToggleRow
            label="Reduce motion"
            description="Turns off animations across Memora, including Mira."
            checked={profile.reduce_motion}
            onChange={(next) => save({ reduce_motion: next })}
          />
          <ToggleRow
            label="High contrast"
            description="Increases contrast between text and backgrounds."
            checked={profile.high_contrast}
            onChange={(next) => save({ high_contrast: next })}
          />
          <ToggleRow
            label="Mute sounds"
            description="Turns off Mira's soft chime sounds."
            checked={profile.mute_sounds}
            onChange={(next) => save({ mute_sounds: next })}
          />
        </CardContent>
      </Card>

      <Card variant="clay">
        <CardHeader>
          <CardTitle>Reading &amp; focus</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div>
            <label className="text-sm font-medium text-foreground" htmlFor="font-pref">
              Font style
            </label>
            <select
              id="font-pref"
              value={profile.font_preference}
              onChange={(e) => save({ font_preference: e.target.value as SensoryProfile["font_preference"] })}
              className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
            >
              <option value="default">Default</option>
              <option value="opendyslexic">OpenDyslexic (easier for some readers)</option>
            </select>
          </div>

          <div>
            <label className="text-sm font-medium text-foreground" htmlFor="attention-span">
              Comfortable session length: {draftAttention} minutes
            </label>
            <input
              id="attention-span"
              type="range"
              min={5}
              max={45}
              step={5}
              value={draftAttention}
              onChange={(e) => setDraftAttention(Number(e.target.value))}
              onMouseUp={(e) => save({ attention_span_minutes: Number((e.target as HTMLInputElement).value) })}
              onTouchEnd={(e) => save({ attention_span_minutes: Number((e.target as HTMLInputElement).value) })}
              className="mt-2 w-full accent-primary"
            />
          </div>
        </CardContent>
      </Card>

      <div className="flex items-center justify-between">
        <button
          onClick={resetToDefaults}
          className="flex items-center gap-1.5 rounded-md border border-border px-3 py-2 text-sm text-muted-foreground hover:bg-muted"
        >
          <RotateCcw className="h-4 w-4" />
          Reset to defaults
        </button>

        <span className="flex items-center gap-1.5 text-xs text-muted-foreground" aria-live="polite">
          {saving ? (
            "Saving..."
          ) : saveError ? (
            <span className="text-error-600">Couldn't save — try again.</span>
          ) : savedAt ? (
            <>
              <Save className="h-3.5 w-3.5 text-success-600" /> Saved
            </>
          ) : null}
        </span>
      </div>
    </div>
  );
}
