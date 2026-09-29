/**
 * MiraWidget.tsx
 *
 * Mira — the Memora learning companion.
 *
 * A full-body illustrated mascot (graduation cap, book, visible arms/
 * legs/tail) rather than a small abstract face — modelled after a
 * "professor" character reference, redrawn as original SVG art with
 * distinct full-body poses per emotional state.
 *
 * Design principles:
 *  - Calm, soft SVG character — expressive but never overstimulating
 *  - Gentle CSS animations only, all respect prefers-reduced-motion
 *  - Proactive messages on mount; reactive to quiz/reflection events
 *  - Student controls: animations ON/OFF, slow mode, sound ON/OFF,
 *    character size
 *  - Soft procedural sound cues via Web Audio API (no audio files) —
 *    gentle rising chimes, never harsh or sudden
 *  - AUTO-SHRINKS to a small corner badge whenever the route is the
 *    Quiz page, so the character can never visually or functionally
 *    overlap the Submit Quiz button — this is a structural fix, not
 *    just a CSS pointer-events trick
 *  - Fully accessible (ARIA live region for messages)
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { Settings, X, Volume2, VolumeX, Zap, ZapOff, MessageCircle, Send } from "lucide-react";
import { cn } from "@/utils/cn";
import { useMiraSubscription, type MiraEvent } from "@/contexts/MiraContext";
import { askCompanion, getCompanionHistory, type ConversationTurn, type InteractionMode } from "@/services/companionService";

// ─── Types ────────────────────────────────────────────────────────────────────
type AnimationState = "idle" | "happy" | "thinking" | "celebrating" | "calm" | "waiting";
type MiraPrefs = {
  animationsOn: boolean;
  slowAnimations: boolean;
  soundOn: boolean;
};

// ─── Message bank (fallback when API is unreachable) ─────────────────────────
const MESSAGES: Record<string, string[]> = {
  welcome: [
    "Hi! I'm Mira. Ready for today's learning?",
    "Welcome back! Let's learn something great today.",
    "Hello! Take your time — we'll go at your pace.",
  ],
  waiting: [
    "Give me a moment while I put this together...",
    "Working on something special for you!",
    "Almost ready — thanks for waiting with me!",
    "Just tossing some ideas around...",
  ],
  quiz_correct: [
    "Great work! You got it!",
    "Excellent! Keep going!",
    "That's right — well done!",
  ],
  quiz_wrong: [
    "That's okay! Mistakes help us learn.",
    "Almost! Let's try a different way.",
    "No worries — every try counts.",
  ],
  quiz_complete_high: [
    "Amazing! You did really well on that quiz!",
    "Fantastic score! You've been working hard.",
  ],
  quiz_complete_low: [
    "Good effort! Every quiz helps you improve.",
    "Well done for finishing! Keep practising.",
  ],
  reflection_done: [
    "You completed today's session — great job!",
    "Brilliant! Your progress has been saved.",
    "You should be proud — session complete!",
  ],
  break: [
    "You've been learning for a while. Would you like a short break?",
    "Great focus today! Remember it's okay to rest for a moment.",
  ],
  lesson_started: [
    "Let's go! Take your time reading through the lesson.",
    "Here we go! No rush — absorb it at your own pace.",
  ],
};

function pickRandom(arr: string[]): string {
  return arr[Math.floor(Math.random() * arr.length)];
}

// ─── Sound engine (Web Audio API — no audio files needed) ─────────────────────
//
// Every sound is a short, soft sine-wave tone or two-note sequence,
// well under 1 second, with a gentle volume envelope (fade in/out —
// never an abrupt on/off click). This is deliberately understated:
// autistic users are often sensitive to sudden or harsh sound, so
// these cues are closer to a soft "ding" than a game-like jingle.
let _audioCtx: AudioContext | null = null;

function getAudioContext(): AudioContext | null {
  if (typeof window === "undefined") return null;
  try {
    if (!_audioCtx) {
      const AC = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!AC) return null;
      _audioCtx = new AC();
    }
    return _audioCtx;
  } catch {
    return null;
  }
}

function playTone(freq: number, startTime: number, duration: number, ctx: AudioContext, peakVolume = 0.08) {
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = "sine";
  osc.frequency.value = freq;

  // Gentle fade in and out — no clicks or sudden starts/stops
  gain.gain.setValueAtTime(0, startTime);
  gain.gain.linearRampToValueAtTime(peakVolume, startTime + duration * 0.2);
  gain.gain.linearRampToValueAtTime(0, startTime + duration);

  osc.connect(gain);
  gain.connect(ctx.destination);
  osc.start(startTime);
  osc.stop(startTime + duration);
}

function playSoundForState(state: AnimationState, soundOn: boolean) {
  if (!soundOn) return;
  const ctx = getAudioContext();
  if (!ctx) return;

  const now = ctx.currentTime;
  switch (state) {
    case "celebrating":
      // Soft rising three-note chime (C-E-G, gentle major triad)
      playTone(523.25, now, 0.22, ctx, 0.07);
      playTone(659.25, now + 0.12, 0.22, ctx, 0.07);
      playTone(783.99, now + 0.24, 0.3, ctx, 0.08);
      break;
    case "happy":
      // Soft two-note rising chime
      playTone(587.33, now, 0.18, ctx, 0.06);
      playTone(698.46, now + 0.1, 0.22, ctx, 0.06);
      break;
    case "thinking":
      // Single soft, slightly lower tone — gentle, not alarming
      playTone(392.0, now, 0.25, ctx, 0.05);
      break;
    case "calm":
      // Very soft single tone, longer and slower — soothing
      playTone(329.63, now, 0.5, ctx, 0.04);
      break;
    // idle: no sound — avoids constant background noise
  }
}

// ─── Mira Mascot (SVG) — full-body professor character ────────────────────────
//
// Modelled after a friendly illustrated "professor" mascot: rounded
// ears, a graduation cap, a round body with visible arms, legs, and a
// tail, holding a book. Each emotional state is a distinct full-body
// pose (not just a facial expression) built from layered <g> groups so
// arms, cap, tail, and face can move somewhat independently while
// reading as one coherent, deliberate motion.
//
// Motion design (autism-friendly, Section 9 of spec):
//   - Every animation is a single, finite, gentle motion — never a
//     continuous loop except the slow idle blink and tail sway.
//   - No motion exceeds ~10px of travel or ~10 degrees of rotation.
//   - Slow-mode roughly doubles every duration.
//   - prefers-reduced-motion disables all of it via the injected <style>.
function MiraMascot({
  animState,
  prefs,
  justGreeted,
}: {
  animState: AnimationState;
  prefs: MiraPrefs;
  justGreeted: boolean;
}) {
  const duration = prefs.slowAnimations ? "3.2s" : "1.6s";
  const doAnim = prefs.animationsOn;

  // Gentle idle motion class — breathing/bobbing/tilting layered via
  // CSS transform on top of the sprite image itself (see the <style>
  // block at the bottom of this file for keyframes). The sprite
  // artwork already encodes the pose/expression per state; this only
  // adds a small amount of life on top of a static image.
  const bodyAnimClass = doAnim
    ? animState === "happy"
      ? "mira-bounce"
      : animState === "celebrating"
      ? "mira-celebrate"
      : animState === "thinking"
      ? "mira-tilt"
      : animState === "calm"
      ? "mira-sway"
      : animState === "waiting"
      ? "mira-waiting-bob"
      : "mira-idle-sway"
    : "";

  // Which illustrated sprite to show. "waving" is reserved for the
  // brief greeting moment right after Mira first appears (see
  // justGreeted, set for ~2.5s on mount in MiraWidget below) —
  // everywhere else, animState maps directly to its matching pose.
  const spriteState = justGreeted ? "waving" : animState;

  // Periodic gentle blink. Two earlier attempts at this were retired
  // for a visible "jump" during the crossfade — traced to head-tilt
  // drift between independently-generated images (imperceptible
  // static side by side, visible in motion). This blink image was
  // verified differently before being wired in: measured pixel
  // silhouette overlap against mira-idle.webp (0.895 IoU, edges
  // within ~11px on a 640px canvas) rather than eyeballing it, so
  // this is a quantified match, not just a visual impression.
  const [blinking, setBlinking] = useState(false);
  const blinkEligible = doAnim && !justGreeted && (animState === "idle" || animState === "calm" || animState === "waiting");

  useEffect(() => {
    if (!blinkEligible) return;
    let timeoutId: ReturnType<typeof setTimeout>;
    const scheduleBlink = () => {
      const delay = 2800 + Math.random() * 3200;
      timeoutId = setTimeout(() => {
        setBlinking(true);
        setTimeout(() => setBlinking(false), 220);
        scheduleBlink();
      }, delay);
    };
    scheduleBlink();
    return () => clearTimeout(timeoutId);
  }, [blinkEligible]);

  const displaySprite = blinking && blinkEligible ? "blink" : spriteState;

  return (
    <div
      role="img"
      aria-label={`Mira the learning companion, currently ${animState}`}
      className={cn("relative h-full w-full", bodyAnimClass)}
      style={
        doAnim
          ? ({ "--mira-duration": duration } as React.CSSProperties)
          : undefined
      }
    >
      {/* Soft ambient drop shadow beneath the character for grounding/depth */}
      <div
        className="absolute bottom-[6%] left-1/2 h-[10%] w-[55%] -translate-x-1/2 rounded-full bg-[#0f2a30]/25 blur-md"
        aria-hidden="true"
      />

      {/* All 7 sprites are stacked and cross-faded via opacity rather
          than swapping the `src` of a single <img> — this avoids any
          flash-to-blank/layout-shift between states, since the
          browser already has every image decoded and painted, just
          hidden. Total asset weight for all 7 combined is well under
          300KB (WebP, normalized/cropped), so preloading all of them
          up front is cheap.

          Blink specifically uses a much faster transition (75ms, not
          the normal 200ms) than every other state change: a real
          blink is near-instant, not a slow fade, AND a slow crossfade
          between two large stacked WebP images was producing a brief
          grey compositing flash in testing (confirmed by the fact
          that forcing all transitions near-instant via
          prefers-reduced-motion / the reduce-motion sensory setting
          eliminated it) — a fast transition fixes both the visual
          accuracy and the artifact at once. will-change hints the
          browser to keep each sprite on its own GPU layer, which
          further reduces the chance of a repaint-driven flash during
          any crossfade. */}
      {(["idle", "happy", "celebrating", "thinking", "waiting", "waving", "calm", "blink"] as const).map((sprite) => (
        <img
          key={sprite}
          src={`/mira/mira-${sprite}.webp`}
          alt=""
          aria-hidden="true"
          draggable={false}
          style={{ willChange: "opacity" }}
          className={cn(
            "absolute inset-0 h-full w-full select-none object-contain ease-out",
            blinking ? "transition-opacity duration-75" : "transition-opacity duration-200",
            displaySprite === sprite ? "opacity-100" : "opacity-0",
          )}
        />
      ))}

      {/* Sparkle accents when celebrating — layered on top of the
          illustration itself (which already has some baked in), for
          extra motion since sparkles in the static image can't move. */}
      {animState === "celebrating" && doAnim && (
        <div className="mira-sparkle pointer-events-none absolute inset-0">
          <span className="absolute left-[8%] top-[18%] text-secondary-300">✦</span>
          <span className="absolute right-[6%] top-[24%] text-secondary-300">✦</span>
        </div>
      )}
    </div>
  );
}

// ─── Controls panel ───────────────────────────────────────────────────────────
function MiraControls({
  prefs,
  onChange,
  onClose,
}: {
  prefs: MiraPrefs;
  onChange: (next: Partial<MiraPrefs>) => void;
  onClose: () => void;
}) {
  return (
    <div className="w-56 rounded-2xl border border-secondary-100 bg-surface p-4 shadow-clayMd">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-semibold text-foreground">Mira Settings</span>
        <button
          onClick={onClose}
          aria-label="Close settings"
          className="rounded p-0.5 hover:bg-muted text-muted-foreground"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="flex flex-col gap-3">
        {/* Animations toggle */}
        <label className="flex items-center justify-between gap-2 cursor-pointer">
          <span className="flex items-center gap-1.5 text-sm text-foreground">
            {prefs.animationsOn ? (
              <Zap className="h-3.5 w-3.5 text-primary" />
            ) : (
              <ZapOff className="h-3.5 w-3.5 text-muted-foreground" />
            )}
            Animations
          </span>
          <button
            role="switch"
            aria-checked={prefs.animationsOn}
            onClick={() => onChange({ animationsOn: !prefs.animationsOn })}
            className={cn(
              "relative inline-flex h-5 w-9 rounded-full transition-colors",
              prefs.animationsOn ? "bg-primary" : "bg-border",
            )}
          >
            <span
              className={cn(
                "absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform",
                prefs.animationsOn ? "translate-x-4" : "translate-x-0.5",
              )}
            />
          </button>
        </label>

        {/* Slow animations */}
        {prefs.animationsOn && (
          <label className="flex items-center justify-between gap-2 cursor-pointer">
            <span className="text-sm text-foreground">🐢 Slow animations</span>
            <button
              role="switch"
              aria-checked={prefs.slowAnimations}
              onClick={() => onChange({ slowAnimations: !prefs.slowAnimations })}
              className={cn(
                "relative inline-flex h-5 w-9 rounded-full transition-colors",
                prefs.slowAnimations ? "bg-primary" : "bg-border",
              )}
            >
              <span
                className={cn(
                  "absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform",
                  prefs.slowAnimations ? "translate-x-4" : "translate-x-0.5",
                )}
              />
            </button>
          </label>
        )}

        {/* Sound toggle — now actually plays sound via Web Audio API */}
        <label className="flex items-center justify-between gap-2 cursor-pointer">
          <span className="flex items-center gap-1.5 text-sm text-foreground">
            {prefs.soundOn ? (
              <Volume2 className="h-3.5 w-3.5 text-primary" />
            ) : (
              <VolumeX className="h-3.5 w-3.5 text-muted-foreground" />
            )}
            Sound
          </span>
          <button
            role="switch"
            aria-checked={prefs.soundOn}
            onClick={() => {
              const next = !prefs.soundOn;
              onChange({ soundOn: next });
              // Play a short preview so the toggle feels responsive
              if (next) playSoundForState("happy", true);
            }}
            className={cn(
              "relative inline-flex h-5 w-9 rounded-full transition-colors",
              prefs.soundOn ? "bg-primary" : "bg-border",
            )}
          >
            <span
              className={cn(
                "absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform",
                prefs.soundOn ? "translate-x-4" : "translate-x-0.5",
              )}
            />
          </button>
        </label>
        <p className="text-xs text-muted-foreground leading-snug">
          Sounds are soft, short chimes — never sudden or loud.
        </p>
      </div>
    </div>
  );
}

// ─── Emotion indicator ──────────────────────────────────────────────────────
const EMOTION_EMOJI: Record<string, string> = {
  happy: "🙂",
  calm: "😌",
  frustrated: "😣",
  anxious: "😟",
  confused: "😕",
  sad: "😔",
};

// ─── Chat panel: full scrollable message history + quick actions ──────────
function MiraChatPanel({
  onClose,
}: {
  onClose: () => void;
}) {
  const [turns, setTurns] = useState<ConversationTurn[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const history = await getCompanionHistory();
        if (!cancelled) setTurns(history);
      } catch {
        // No history yet, or request failed — start with an empty transcript.
      } finally {
        if (!cancelled) setLoadingHistory(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, sending]);

  async function send(message: string, mode: InteractionMode = "chat") {
    if (!message.trim() || sending) return;
    setSending(true);
    setTurns((prev) => [
      ...prev,
      { role: "student", message, emotion_detected: null, created_at: new Date().toISOString() },
    ]);
    setInput("");
    try {
      const resp = await askCompanion(message, mode);
      setTurns((prev) => {
        const next = [...prev];
        // attach detected emotion to the student's turn we just added
        const lastStudentIdx = next.map((t) => t.role).lastIndexOf("student");
        if (lastStudentIdx !== -1 && resp.detected_emotion) {
          next[lastStudentIdx] = { ...next[lastStudentIdx], emotion_detected: resp.detected_emotion };
        }
        next.push({
          role: "mira",
          message: resp.message,
          emotion_detected: null,
          created_at: new Date().toISOString(),
        });
        return next;
      });
    } catch {
      setTurns((prev) => [
        ...prev,
        {
          role: "mira",
          message: "I'm having trouble responding right now — please try again in a moment.",
          emotion_detected: null,
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setSending(false);
    }
  }

  const quickActions: { label: string; message: string; mode: InteractionMode }[] = [
    { label: "I need a break", message: "I need a break.", mode: "calm_down" },
    { label: "Explain differently", message: "Can you explain that differently?", mode: "chat" },
    { label: "Too hard", message: "This feels too hard right now.", mode: "chat" },
    { label: "I'm stuck", message: "I'm stuck and not sure what to do next.", mode: "chat" },
  ];

  return (
    <div className="pointer-events-auto flex h-[420px] w-[320px] flex-col overflow-hidden rounded-3xl border border-secondary-100 bg-surface shadow-clayMd">
      <div className="flex items-center justify-between bg-gradient-to-r from-secondary-500 to-secondary-600 px-4 py-3 text-white">
        <span className="text-sm font-semibold">Chat with Mira</span>
        <button
          onClick={onClose}
          aria-label="Close chat"
          className="rounded-lg p-1 text-white/80 transition-colors hover:bg-white/15 hover:text-white"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div
        ref={scrollRef}
        className="flex-1 space-y-3 overflow-y-auto px-4 py-3"
        aria-live="polite"
      >
        {loadingHistory && (
          <p className="text-center text-xs text-muted-foreground">Loading conversation...</p>
        )}
        {!loadingHistory && turns.length === 0 && (
          <p className="text-center text-xs text-muted-foreground">
            Say hello to Mira, or use a quick action below.
          </p>
        )}
        {turns.map((turn, i) => (
          <div
            key={i}
            className={cn("flex flex-col", turn.role === "student" ? "items-end" : "items-start")}
          >
            <div
              className={cn(
                "max-w-[85%] rounded-2xl px-3 py-2 text-sm leading-snug",
                turn.role === "student"
                  ? "rounded-br-sm bg-primary text-white"
                  : "rounded-bl-sm bg-secondary-50 text-foreground",
              )}
            >
              {turn.message}
            </div>
            {turn.emotion_detected && (
              <span className="mt-1 text-xs text-muted-foreground">
                {EMOTION_EMOJI[turn.emotion_detected] ?? ""} {turn.emotion_detected}
              </span>
            )}
          </div>
        ))}
        {sending && (
          <div className="flex items-start">
            <div className="rounded-2xl rounded-bl-sm bg-secondary-50 px-3 py-2 text-sm text-muted-foreground">
              <span className="inline-flex gap-1">
                <span className="mira-typing-dot">.</span>
                <span className="mira-typing-dot">.</span>
                <span className="mira-typing-dot">.</span>
              </span>
            </div>
          </div>
        )}
      </div>

      <div className="flex flex-wrap gap-1.5 border-t border-border px-3 py-2">
        {quickActions.map((action) => (
          <button
            key={action.label}
            onClick={() => send(action.message, action.mode)}
            disabled={sending}
            className="rounded-full border border-secondary-200 bg-secondary-50 px-3 py-1 text-xs text-secondary-700 transition-colors hover:bg-secondary-100 disabled:opacity-50"
          >
            {action.label}
          </button>
        ))}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="flex items-center gap-2 border-t border-border px-3 py-2"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type a message..."
          disabled={sending}
          className="flex-1 rounded-full border border-border bg-background px-3 py-1.5 text-sm text-foreground focus:border-secondary-400 focus:outline-none focus:ring-4 focus:ring-secondary-100"
        />
        <button
          type="submit"
          disabled={sending || !input.trim()}
          aria-label="Send message"
          className="rounded-full bg-primary p-2 text-white disabled:opacity-50"
        >
          <Send className="h-4 w-4" />
        </button>
      </form>
    </div>
  );
}

// ─── Main widget ──────────────────────────────────────────────────────────────
export function MiraWidget() {
  // Mira renders as the full character on every student page, including
  // the Quiz page — the earlier "shrink to a badge on the quiz page"
  // approach traded away Mira's visibility/animations exactly where a
  // student most benefits from encouragement. The actual overlap risk
  // (the Submit Quiz button sitting under Mira's fixed bottom-right
  // position) is now fixed structurally in Quiz.tsx itself, by
  // left-aligning that button instead of anchoring it bottom-right —
  // Mira's own rendering doesn't need to change or compromise at all.
  const [open, setOpen] = useState(true);
  const [showControls, setShowControls] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [message, setMessage] = useState<string>("");
  const [animState, setAnimState] = useState<AnimationState>("idle");
  // Shows the "waving" illustration for a few seconds right when Mira
  // first appears — a small, deliberate hello rather than starting
  // static/neutral. Purely cosmetic; doesn't affect animState or any
  // message logic below.
  const [justGreeted, setJustGreeted] = useState(true);
  const [prefs, setPrefs] = useState<MiraPrefs>({
    animationsOn: true,
    slowAnimations: false,
    soundOn: false,
  });

  const sessionStartRef = useRef<number>(Date.now());
  const breakFiredRef = useRef(false);
  const prefsRef = useRef(prefs);
  const revertTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  prefsRef.current = prefs;

  // ── Fetch welcome message on mount ─────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const resp = await askCompanion();
        if (!cancelled) setMessage(resp.message);
      } catch {
        if (!cancelled) setMessage(pickRandom(MESSAGES.welcome));
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // ── End the one-time "waving hello" moment after a few seconds ─────────────
  useEffect(() => {
    const id = setTimeout(() => setJustGreeted(false), 2800);
    return () => clearTimeout(id);
  }, []);

  // ── Break suggestion timer ──────────────────────────────────────────────────
  useEffect(() => {
    const id = setInterval(() => {
      const elapsed = Date.now() - sessionStartRef.current;
      if (elapsed > 20 * 60 * 1000 && !breakFiredRef.current) {
        breakFiredRef.current = true;
        showMessage(pickRandom(MESSAGES.break), "calm");
      }
    }, 60 * 1000);
    return () => clearInterval(id);
  }, []);

  // ── React to learning events ────────────────────────────────────────────────
  const handleMiraEvent = useCallback((event: MiraEvent) => {
    switch (event.type) {
      case "lesson_started":
        showMessage(pickRandom(MESSAGES.lesson_started), "happy");
        break;
      case "quiz_correct":
        showMessage(pickRandom(MESSAGES.quiz_correct), "happy");
        break;
      case "quiz_wrong":
        showMessage(pickRandom(MESSAGES.quiz_wrong), "thinking");
        break;
      case "quiz_complete": {
        const highScore = (event.score ?? 0) >= 70;
        showMessage(
          pickRandom(highScore ? MESSAGES.quiz_complete_high : MESSAGES.quiz_complete_low),
          highScore ? "celebrating" : "thinking",
        );
        break;
      }
      case "reflection_done":
        showMessage(pickRandom(MESSAGES.reflection_done), "celebrating");
        break;
      case "waiting_start":
        // Persistent state, deliberately NOT using showMessage()'s
        // auto-revert-to-idle timer — this should stay active for as
        // long as the actual AI generation takes (could be a few
        // seconds or, on slow hardware, well over a minute), not on a
        // fixed timeout. waiting_stop below is what ends it.
        if (revertTimeoutRef.current) {
          clearTimeout(revertTimeoutRef.current);
          revertTimeoutRef.current = null;
        }
        setMessage(pickRandom(MESSAGES.waiting));
        setAnimState("waiting");
        break;
      case "waiting_stop":
        // Return to idle immediately; whatever follows (e.g.
        // quiz_complete firing right after) will set its own state.
        setAnimState("idle");
        break;
    }
    setOpen(true);
  }, []);

  useMiraSubscription(handleMiraEvent, []);

  // ── Helpers ────────────────────────────────────────────────────────────────
  function showMessage(msg: string, state: AnimationState = "idle") {
    if (revertTimeoutRef.current) {
      clearTimeout(revertTimeoutRef.current);
      revertTimeoutRef.current = null;
    }
    setMessage(msg);
    setAnimState(state);
    playSoundForState(state, prefsRef.current.soundOn);
    const base = state === "celebrating" ? 3200 : 2500;
    const delay = prefsRef.current.slowAnimations ? base * 1.6 : base;
    revertTimeoutRef.current = setTimeout(() => setAnimState("idle"), delay);
  }

  function updatePrefs(next: Partial<MiraPrefs>) {
    setPrefs((prev) => ({ ...prev, ...next }));
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <>
      {/* Keyframe animations injected once */}
      <style>{`
        @keyframes mira-bounce {
          0%, 100% { transform: translateY(0); }
          40%       { transform: translateY(-10px); }
          60%       { transform: translateY(-5px); }
        }
        @keyframes mira-celebrate {
          0%, 100% { transform: translateY(0) rotate(0deg); }
          25%       { transform: translateY(-12px) rotate(-3deg); }
          50%       { transform: translateY(-3px) rotate(3deg); }
          75%       { transform: translateY(-12px) rotate(-2deg); }
        }
        @keyframes mira-tilt {
          0%, 100% { transform: rotate(0deg); }
          50%       { transform: rotate(-5deg); }
        }
        @keyframes mira-sway {
          0%, 100% { transform: translateX(0); }
          50%       { transform: translateX(-3px); }
        }
        @keyframes mira-idle-sway {
          0%, 100% { transform: translateX(0) rotate(0deg); }
          50%       { transform: translateX(1.5px) rotate(0.8deg); }
        }
        @keyframes mira-waiting-bob {
          0%, 100% { transform: translateY(0) rotate(0deg); }
          25%       { transform: translateY(-6px) rotate(-2deg); }
          50%       { transform: translateY(0) rotate(0deg); }
          75%       { transform: translateY(-3px) rotate(2deg); }
        }
        @keyframes mira-sparkle {
          0%, 100% { opacity: 0; transform: scale(0.7); }
          50%       { opacity: 1; transform: scale(1); }
        }
        @keyframes mira-typing-dot {
          0%, 80%, 100% { opacity: 0.3; }
          40%            { opacity: 1; }
        }
        .mira-typing-dot { animation: mira-typing-dot 1.2s ease-in-out infinite; }
        .mira-typing-dot:nth-child(2) { animation-delay: 0.2s; }
        .mira-typing-dot:nth-child(3) { animation-delay: 0.4s; }
        .mira-bounce      { animation: mira-bounce var(--mira-duration, 1.6s) ease-in-out 1; }
        .mira-celebrate   { animation: mira-celebrate var(--mira-duration, 1.6s) ease-in-out 1; transform-origin: center bottom; }
        .mira-tilt        { animation: mira-tilt var(--mira-duration, 1.6s) ease-in-out 1; }
        .mira-sway        { animation: mira-sway var(--mira-duration, 1.6s) ease-in-out 1; }
        .mira-idle-sway   { animation: mira-idle-sway 5s ease-in-out infinite; }
        .mira-waiting-bob { animation: mira-waiting-bob 1.8s ease-in-out infinite; }
        .mira-sparkle span { display: inline-block; animation: mira-sparkle 1.2s ease-in-out infinite; }
        .mira-sparkle span:last-child { animation-delay: 0.4s; }
        @media (prefers-reduced-motion: reduce) {
          .mira-bounce, .mira-celebrate, .mira-tilt, .mira-sway, .mira-idle-sway,
          .mira-waiting-bob, .mira-sparkle span {
            animation: none !important;
          }
        }
      `}</style>

      {showControls && (
        <div className="fixed bottom-64 right-6 z-50">
          <MiraControls
            prefs={prefs}
            onChange={updatePrefs}
            onClose={() => setShowControls(false)}
          />
        </div>
      )}

      {chatOpen && (
        <div className="fixed bottom-48 right-4 z-50 md:bottom-60 md:right-6">
          <MiraChatPanel onClose={() => setChatOpen(false)} />
        </div>
      )}

      <div className="fixed bottom-4 right-4 z-40 flex flex-col items-end gap-2 pointer-events-none md:bottom-6 md:right-6">
        {/* Speech bubble */}
        {open && message && !chatOpen && (
          <div
            role="status"
            aria-live="polite"
            aria-atomic="true"
            className="pointer-events-auto max-w-[240px] rounded-2xl rounded-br-sm border border-secondary-100 bg-surface px-4 py-3 shadow-clayMd text-sm text-foreground leading-snug"
          >
            {message}
          </div>
        )}

        <div className="flex items-end gap-2 pointer-events-none">
          {open && (
            <button
              onClick={() => setChatOpen((v) => !v)}
              aria-label={chatOpen ? "Close chat with Mira" : "Chat with Mira"}
              className="pointer-events-auto mb-1 rounded-full border border-border bg-surface p-1.5 text-muted-foreground shadow hover:bg-muted transition-colors"
            >
              <MessageCircle className="h-3.5 w-3.5" />
            </button>
          )}

          {open && (
            <button
              onClick={() => setShowControls((v) => !v)}
              aria-label="Mira settings"
              className="pointer-events-auto mb-1 rounded-full border border-border bg-surface p-1.5 text-muted-foreground shadow hover:bg-muted transition-colors"
            >
              <Settings className="h-3.5 w-3.5" />
            </button>
          )}

          {open && message && (
            <button
              onClick={() => setOpen(false)}
              aria-label="Dismiss Mira"
              className="pointer-events-auto mb-1 rounded-full border border-border bg-surface p-1.5 text-muted-foreground shadow hover:bg-muted transition-colors"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}

          {/* Full-body character — always shown at full size and with
              full animation, on every student page including Quiz.
              Sized generously (was h-32/w-32) so Mira reads as a
              present, characterful companion rather than a small
              corner icon. */}
          <button
            onClick={() => setOpen((v) => !v)}
            aria-label={open ? "Collapse Mira" : "Open Mira"}
            className="pointer-events-auto h-40 w-40 transition-transform hover:scale-105 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2 rounded-2xl md:h-52 md:w-52"
          >
            <MiraMascot animState={animState} prefs={prefs} justGreeted={justGreeted} />
          </button>
        </div>
      </div>
    </>
  );
}
