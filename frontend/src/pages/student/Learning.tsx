import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { BookOpen, PlayCircle, StickyNote } from "lucide-react";

import { AILoadingState } from "@/components/ai/AILoadingState";
import { useMira } from "@/contexts/MiraContext";
import { useSessionEngagementTracker } from "@/hooks/useSessionEngagementTracker";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ListenButton } from "@/components/ui/ListenButton";
import { useSensory } from "@/contexts/SensoryContext";
import {
  abandonSession,
  getContentForSession,
  getSessionById,
  type LearningContent,
  type LearningSession,
} from "@/services/studentLearningService";

// ─── Video player ─────────────────────────────────────────────────────────────
function VideoPlayer({ url }: { url: string }) {
  // Detect YouTube URLs and convert to embed format
  const youtubeMatch = url.match(
    /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([A-Za-z0-9_-]{11})/
  );

  if (youtubeMatch) {
    const videoId = youtubeMatch[1];
    return (
      <div className="relative w-full overflow-hidden rounded-lg bg-black" style={{ paddingTop: "56.25%" }}>
        <iframe
          className="absolute inset-0 h-full w-full"
          src={`https://www.youtube.com/embed/${videoId}?rel=0&modestbranding=1`}
          title="Lesson video"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowFullScreen
        />
      </div>
    );
  }

  // Direct video file (MP4 etc.)
  return (
    <video
      controls
      className="w-full rounded-lg bg-black"
      style={{ maxHeight: "400px" }}
      src={url}
    >
      Your browser doesn't support video playback.
    </video>
  );
}

// ─── Difficulty badge (color-coded, low-key not alarming) ────────────────────
function DifficultyBadge({ level }: { level: string }) {
  const styles: Record<string, string> = {
    Beginner: "bg-success-50 text-success-600 border-success-200",
    Intermediate: "bg-warning-50 text-warning-600 border-warning-200",
    Advanced: "bg-secondary-50 text-secondary-600 border-secondary-200",
  };
  const style = styles[level] ?? "bg-muted text-muted-foreground border-border";
  return (
    <span className={`inline-flex shrink-0 items-center rounded-full border px-3 py-1 text-xs font-medium ${style}`}>
      {level}
    </span>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────
export function Learning() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const sessionId = Number(searchParams.get("session"));

  const { pushMiraEvent } = useMira();
  const { profile: sensoryProfile } = useSensory();
  useSessionEngagementTracker(sessionId || null);
  const [session, setSession] = useState<LearningSession | null>(null);
  const [content, setContent] = useState<LearningContent | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState(false);
  const [abandoning, setAbandoning] = useState(false);

  useEffect(() => {
    if (!sessionId) { setError(true); return; }
    let cancelled = false;

    (async () => {
      try {
        const foundSession = await getSessionById(sessionId);
        if (!foundSession) { if (!cancelled) setError(true); return; }
        if (!cancelled) setSession(foundSession);

        // Fetch the EXACT content this session was assigned — never
        // re-derive via the recommendation engine, which would return
        // a different entry whenever the plan has more than one active
        // piece of content at the same difficulty level.
        const sessionContent = await getContentForSession(sessionId);
        if (!cancelled) setContent(sessionContent);
      } catch (err) {
        const status = (err as { response?: { status?: number } })?.response?.status;
        if (status === 404) {
          if (!cancelled) setNotFound(true);
        } else if (!cancelled) {
          setError(true);
        }
      }
    })();

    return () => { cancelled = true; };
  }, [sessionId]);

  async function handleAbandon() {
    setAbandoning(true);
    try {
      await abandonSession(sessionId);
      navigate("/student", { replace: true });
    } catch {
      setAbandoning(false);
    }
  }


  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-3">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary-50">
          <BookOpen className="h-6 w-6 text-primary-600" aria-hidden="true" />
        </span>
        <div>
          <h1 className="text-2xl font-bold text-foreground">Today's Lesson</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Read through carefully — take all the time you need.
          </p>
        </div>
      </div>

      {!sessionId || error ? (
        <EmptyState
          icon={BookOpen}
          title="No lesson loaded"
          description="Go back to Today's Learning and choose a session to continue."
        />
      ) : notFound ? (
        <EmptyState
          icon={BookOpen}
          title="Content unavailable"
          description="The content for this session could not be found. It may have been removed by your teacher."
        />
      ) : content === null ? (
        <AILoadingState kind="preparingLesson" />
      ) : (
        <div className="flex flex-col gap-5">
          {/* ── Video section: shown whenever the teacher added one,
                and — when this student's SensoryProfile.preferred_mode
                is "visual" — an honest note if no video exists for
                this lesson, rather than silently doing nothing when a
                student who prefers visual content gets none. ── */}
          {content.video_url ? (
            <Card variant="clay">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <PlayCircle className="h-4 w-4 text-primary-500" aria-hidden="true" />
                  Lesson Video
                </CardTitle>
              </CardHeader>
              <CardContent>
                <VideoPlayer url={content.video_url} />
              </CardContent>
            </Card>
          ) : sensoryProfile?.preferred_mode === "visual" ? (
            <p className="rounded-xl border border-dashed border-border bg-muted/40 px-4 py-3 text-sm text-muted-foreground">
              You've set your preferred mode to visual, but this particular lesson doesn't have a
              video yet — the text and audio below still work the same either way.
            </p>
          ) : null}

          {/* ── Main content card ── */}
          <Card variant="clay">
            <CardHeader>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <CardTitle className="text-xl">{content.title}</CardTitle>
                <DifficultyBadge level={content.difficulty_level} />
              </div>
              {content.subject && (
                <CardDescription>{content.subject}</CardDescription>
              )}
              {/* Auditory content mode: reads the lesson aloud via the
                  browser's built-in text-to-speech. Always available
                  (any student might want it in the moment) — shown
                  with the primary button style, not just outline,
                  specifically when this student's SensoryProfile.
                  preferred_mode is "auditory", so it's the visually
                  emphasized action rather than an equal-weight option
                  they'd have to notice on their own. */}
              <div className="pt-1">
                <ListenButton
                  text={`${content.title}. ${content.body}`}
                  emphasized={sensoryProfile?.preferred_mode === "auditory"}
                />
              </div>
            </CardHeader>
            <CardContent className="flex flex-col gap-6">
              <div className="max-w-prose">
                <p className="whitespace-pre-wrap text-[17px] leading-8 text-foreground">
                  {content.body}
                </p>
              </div>

              {/* ── Teacher notes (shown only if present) ── */}
              {content.teacher_notes && (
                <div className="rounded-xl border-2 border-primary-100 bg-primary-50 p-4">
                  <p className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-primary-600">
                    <StickyNote className="h-3.5 w-3.5" aria-hidden="true" />
                    Teacher's Note
                  </p>
                  <p className="whitespace-pre-wrap text-sm leading-relaxed text-primary-800">
                    {content.teacher_notes}
                  </p>
                </div>
              )}

              {/* ── Action row: normal lesson flow, or a review-mode
                   banner when this lesson was already completed
                   (reached by clicking "Review Lesson" on the
                   Progress page — students can revisit any past
                   lesson's content whenever they want, without
                   re-triggering the quiz/reflection flow or affecting
                   their recorded score). ── */}
              {session?.status === "completed" ? (
                <div className="flex flex-col gap-3 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-sm text-muted-foreground">
                    ✓ You already completed this lesson — you're just reviewing it again.
                  </p>
                  <Button variant="outline" onClick={() => navigate("/student/progress")}>
                    Back to Progress
                  </Button>
                </div>
              ) : (
                <div className="flex flex-wrap gap-3 border-t border-border pt-4">
                  <Button
                    size="lg"
                    onClick={() => {
                      pushMiraEvent({ type: "lesson_started" });
                      navigate(`/student/quiz?session=${sessionId}`);
                    }}
                  >
                    Start Quiz
                  </Button>
                  <Button variant="outline" disabled={abandoning} onClick={handleAbandon}>
                    {abandoning ? "..." : "Not Now"}
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
