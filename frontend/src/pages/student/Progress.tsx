import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { TrendingUp, CheckCircle2, Clock, AlertCircle, RotateCcw } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { getAllSessions, type LearningSession } from "@/services/studentLearningService";

// ─── Helpers ──────────────────────────────────────────────────────────────────
const STATUS_CONFIG: Record<
  LearningSession["status"],
  { label: string; colour: string; icon: typeof Clock }
> = {
  started:   { label: "In Progress",  colour: "text-warning-600 bg-warning-50 border-warning-200",  icon: Clock },
  completed: { label: "Completed",    colour: "text-success-600 bg-success-50 border-success-200",  icon: CheckCircle2 },
  abandoned: { label: "Not Finished", colour: "text-muted-foreground bg-muted border-border",       icon: AlertCircle },
};

function relativeTime(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 2) return "just now";
  if (minutes < 60) return `${minutes} minutes ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hour${hours > 1 ? "s" : ""} ago`;
  const days = Math.floor(hours / 24);
  if (days === 1) return "yesterday";
  if (days < 30) return `${days} days ago`;
  return new Date(dateStr).toLocaleDateString();
}

// ─── Summary stat strip ───────────────────────────────────────────────────────
function SummaryStrip({ sessions }: { sessions: LearningSession[] }) {
  const completed = sessions.filter((s) => s.status === "completed").length;
  const total = sessions.length;
  const pct = total > 0 ? Math.round((completed / total) * 100) : 0;

  return (
    <div className="grid grid-cols-3 gap-4">
      {[
        { label: "Sessions", value: total },
        { label: "Completed", value: completed },
        { label: "Completion rate", value: `${pct}%` },
      ].map(({ label, value }) => (
        <div
          key={label}
          className="flex flex-col items-center justify-center rounded-xl border border-border bg-surface p-4 text-center"
        >
          <p className="text-2xl font-bold text-foreground">{value}</p>
          <p className="mt-0.5 text-xs text-muted-foreground">{label}</p>
        </div>
      ))}
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────
export function Progress() {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState<LearningSession[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getAllSessions()
      .then((data) => { if (!cancelled) setSessions(data); })
      .catch(() => { if (!cancelled) setError(true); });
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-foreground">My Progress</h1>
        <p className="mt-1 text-muted-foreground">
          Track your learning journey over time.
        </p>
      </div>

      {sessions === null && !error && (
        <div className="flex justify-center py-16">
          <LoadingSpinner />
        </div>
      )}

      {error && (
        <EmptyState
          icon={TrendingUp}
          title="Couldn't load your progress"
          description="Something went wrong. Please try again in a moment."
        />
      )}

      {sessions !== null && sessions.length === 0 && (
        <EmptyState
          icon={TrendingUp}
          title="No progress yet"
          description="Complete a learning session to see your progress here."
        />
      )}

      {sessions !== null && sessions.length > 0 && (
        <>
          <SummaryStrip sessions={sessions} />
          <div className="flex flex-col gap-3">
            {sessions.map((session) => {
              const cfg = STATUS_CONFIG[session.status];
              const StatusIcon = cfg.icon;
              return (
                <Card variant="clay" key={session.id}>
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between gap-4">
                      <CardTitle className="text-base">
                        Session #{session.id}
                      </CardTitle>
                      <span
                        className={`inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${cfg.colour}`}
                      >
                        <StatusIcon className="h-3 w-3" aria-hidden="true" />
                        {cfg.label}
                      </span>
                    </div>
                    <CardDescription>
                      Difficulty: {session.difficulty_level_at_session}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">
                      {relativeTime(session.started_at)}
                      {session.completed_at && (
                        <> · Finished {relativeTime(session.completed_at)}</>
                      )}
                    </p>
                    {session.status === "completed" && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="mt-3 gap-1.5"
                        onClick={() => navigate(`/student/learning?session=${session.id}`)}
                      >
                        <RotateCcw className="h-3.5 w-3.5" />
                        Review Lesson Again
                      </Button>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
