import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Sparkles, BookOpen, CheckCircle2, Clock, AlertCircle, Sun, Moon, Sunrise } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import {
  getAllSessions,
  getTodaysLearning,
  type LearningSession,
} from "@/services/studentLearningService";

// ─── Time-of-day greeting banner ──────────────────────────────────────────────
function timeOfDayGreeting(): { label: string; icon: typeof Sun; sub: string } {
  const hour = new Date().getHours();
  if (hour < 12) return { label: "Good morning", icon: Sunrise, sub: "A fresh start for today's learning." };
  if (hour < 17) return { label: "Good afternoon", icon: Sun, sub: "Let's keep the momentum going." };
  return { label: "Good evening", icon: Moon, sub: "A calm session before the day winds down." };
}

function GreetingBanner() {
  const { label, icon: Icon, sub } = timeOfDayGreeting();
  return (
    <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-primary-600 via-primary-500 to-secondary-500 px-6 py-7 text-white shadow-softMd">
      {/* Soft decorative circles — purely ambient, never distracting */}
      <div className="pointer-events-none absolute -right-8 -top-10 h-36 w-36 rounded-full bg-white/10" />
      <div className="pointer-events-none absolute -right-2 bottom-[-2.5rem] h-24 w-24 rounded-full bg-white/10" />
      <div className="relative flex items-center gap-3">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-white/15">
          <Icon className="h-6 w-6" aria-hidden="true" />
        </span>
        <div>
          <h1 className="text-xl font-bold sm:text-2xl">{label}!</h1>
          <p className="mt-0.5 text-sm text-white/90">{sub}</p>
        </div>
      </div>
    </div>
  );
}

// ─── Session status display helpers ──────────────────────────────────────────
const STATUS_CONFIG: Record<
  LearningSession["status"],
  { label: string; colour: string; icon: typeof Clock }
> = {
  started:   { label: "In Progress",  colour: "text-warning-600 bg-warning-50 border-warning-200",   icon: Clock },
  completed: { label: "Completed",    colour: "text-success-600 bg-success-50 border-success-200",   icon: CheckCircle2 },
  abandoned: { label: "Not Finished", colour: "text-muted-foreground bg-muted border-border",        icon: AlertCircle },
};

/** Rough learning-loop progress for a given session status */
function loopStep(status: LearningSession["status"]): number {
  return status === "completed" ? 3 : status === "started" ? 1 : 0;
}

function SessionCard({ session, onContinue }: { session: LearningSession; onContinue: () => void }) {
  const cfg = STATUS_CONFIG[session.status];
  const StatusIcon = cfg.icon;
  const step = loopStep(session.status);
  const steps = ["Lesson", "Quiz", "Reflection"];
  const isComplete = session.status === "completed";

  return (
    <Card variant="clay" className="transition-shadow hover:shadow-clayMd">
      <CardHeader>
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary-50">
              <Sparkles className="h-5 w-5 text-primary-500 shrink-0" aria-hidden="true" />
            </span>
            <CardTitle className="text-base">Today's Session</CardTitle>
          </div>
          <span
            className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${cfg.colour}`}
          >
            <StatusIcon className="h-3 w-3" aria-hidden="true" />
            {cfg.label}
          </span>
        </div>
        <CardDescription className="pl-[46px]">
          Difficulty: {session.difficulty_level_at_session}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        {/* Learning loop progress steps */}
        <div className="flex items-center gap-0" aria-label="Progress through today's session">
          {steps.map((label, index) => {
            const done = step > index;
            const active = step === index && !isComplete;
            return (
              <div key={label} className="flex flex-1 items-center">
                <div className="flex flex-col items-center gap-1 flex-1">
                  <div
                    className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold border-2 transition-colors ${
                      done
                        ? "bg-success-500 border-success-500 text-white"
                        : active
                        ? "bg-primary-50 border-primary-500 text-primary-700 ring-4 ring-primary-100"
                        : "bg-muted border-border text-muted-foreground"
                    }`}
                  >
                    {done ? "✓" : index + 1}
                  </div>
                  <span className={`text-xs ${active ? "text-primary-700 font-medium" : "text-muted-foreground"}`}>
                    {label}
                  </span>
                </div>
                {index < steps.length - 1 && (
                  <div className={`h-0.5 flex-1 mb-4 rounded transition-colors ${done ? "bg-success-400" : "bg-border"}`} />
                )}
              </div>
            );
          })}
        </div>

        {!isComplete && (
          <Button size="lg" onClick={onContinue}>
            {step === 0 ? "Start Learning" : "Continue"}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────
export function StudentDashboard() {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState<LearningSession[] | null>(null);
  // Tracks whether the student has ANY session in their history at all
  // (any status) — used only to distinguish "nothing has ever been
  // assigned" from "everything assigned so far has been completed,"
  // which need very different empty-state messages. Without this,
  // finishing your only session for the day showed the exact same
  // "No lesson assigned yet" message as a brand-new account that has
  // never been given any work — easy to misread as progress having
  // been lost, when it's actually sitting correctly on the Progress
  // page the whole time.
  const [hasAnyHistory, setHasAnyHistory] = useState<boolean | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getTodaysLearning()
      .then((data) => { if (!cancelled) setSessions(data); })
      .catch(() => { if (!cancelled) setError(true); });
    getAllSessions()
      .then((data) => { if (!cancelled) setHasAnyHistory(data.length > 0); })
      .catch(() => { /* non-critical — falls back to the generic empty state */ });
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <GreetingBanner />

      {sessions === null && !error && (
        <div className="flex justify-center py-16">
          <LoadingSpinner />
        </div>
      )}

      {error && (
        <EmptyState
          icon={BookOpen}
          title="Couldn't load your learning"
          description="Something went wrong. Please try again in a moment."
        />
      )}

      {sessions !== null && sessions.length === 0 && hasAnyHistory && (
        <EmptyState
          icon={CheckCircle2}
          title="You're all caught up!"
          description="You've completed everything assigned so far — nice work. Check your Progress page to see how you did, or check back later for your next lesson."
          action={
            <Button variant="outline" onClick={() => navigate("/student/progress")}>
              View My Progress
            </Button>
          }
        />
      )}

      {sessions !== null && sessions.length === 0 && hasAnyHistory === false && (
        <EmptyState
          icon={Sparkles}
          title="No lesson assigned yet"
          description="Your teacher hasn't assigned a learning session yet. Check back soon."
        />
      )}

      {sessions !== null &&
        sessions.map((session) => (
          <SessionCard
            key={session.id}
            session={session}
            onContinue={() => navigate(`/student/learning?session=${session.id}`)}
          />
        ))}
    </div>
  );
}
