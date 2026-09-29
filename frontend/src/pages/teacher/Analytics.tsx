import { FormEvent, useEffect, useState } from "react";
import { BarChart3, Sparkles } from "lucide-react";

import { AILoadingState } from "@/components/ai/AILoadingState";
import { AnalyticsChart, CHART_COLOURS } from "@/components/charts/AnalyticsChart";
import {
  generateEngagementPrediction,
  getAdaptiveSuggestion,
  NoEngagementPredictionError,
  type AdaptiveSuggestion,
} from "@/services/aiService";
import { getModelEvaluation, getStudentAnalytics, type ModelEvaluation, type StudentAnalytics } from "@/services/analyticsService";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { listAllLearningContent, type LearningContentRecord } from "@/services/learningContentService";
import {
  abandonLearningSession,
  listLearningSessions,
  type LearningSessionRecord,
} from "@/services/learningSessionService";
import { listStudents, type StudentRecord } from "@/services/studentService";

export function Analytics() {
  const [students, setStudents] = useState<StudentRecord[]>([]);
  const [selectedStudentId, setSelectedStudentId] = useState<number | null>(null);
  const [analytics, setAnalytics] = useState<StudentAnalytics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [modelEval, setModelEval] = useState<ModelEvaluation | null>(null);
  const [modelEvalError, setModelEvalError] = useState(false);

  const [sessions, setSessions] = useState<LearningSessionRecord[] | null>(null);
  const [content, setContent] = useState<LearningContentRecord[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState("");
  const [suggestion, setSuggestion] = useState<AdaptiveSuggestion | null>(null);
  const [suggestionLoading, setSuggestionLoading] = useState(false);
  const [suggestionError, setSuggestionError] = useState<string | null>(null);
  const [abandonSubmitting, setAbandonSubmitting] = useState(false);
  const [abandonMessage, setAbandonMessage] = useState<string | null>(null);
  const [abandonConfirming, setAbandonConfirming] = useState(false);

  function refreshSessions() {
    listLearningSessions()
      .then(setSessions)
      .catch(() => setSuggestionError("Couldn't load learning sessions."));
  }

  useEffect(() => {
    listStudents()
      .then((data) => {
        setStudents(data);
        if (data.length > 0) setSelectedStudentId(data[0].id);
      })
      .catch(() => setError("Couldn't load your students."));

    // Sessions + content are loaded once, up front, so the Adaptive
    // Suggestion picker below can show meaningful "student — content"
    // labels instead of asking the teacher to know a raw session ID.
    refreshSessions();
    listAllLearningContent()
      .then(setContent)
      .catch(() => {
        /* Content is only used for display labels below; a failure
           here just falls back to showing content id instead of title. */
      });

    // Model evaluation metrics are global (not per-student) and
    // inexpensive to compute (300 samples, single tree), so fetch once
    // on mount rather than re-fetching whenever the selected student
    // changes.
    getModelEvaluation()
      .then(setModelEval)
      .catch(() => setModelEvalError(true));
  }, []);

  useEffect(() => {
    if (selectedStudentId === null) return;
    setAnalytics(null);
    getStudentAnalytics(selectedStudentId)
      .then(setAnalytics)
      .catch(() => setError("Couldn't load analytics for this student."));
  }, [selectedStudentId]);

  function studentName(id: number): string {
    return students.find((s) => s.id === id)?.full_name ?? `Student #${id}`;
  }

  function contentTitle(id: number): string {
    return content.find((c) => c.id === id)?.title ?? `Content #${id}`;
  }

  async function handleGetSuggestion(event: FormEvent) {
    event.preventDefault();
    const sessionId = Number(selectedSessionId);
    if (!sessionId) return;

    setSuggestion(null);
    setSuggestionError(null);
    setSuggestionLoading(true);
    try {
      // The rule engine needs an engagement prediction to work from.
      // Generating is idempotent-safe here: if one already exists this
      // call fails harmlessly and we proceed straight to reading the
      // suggestion from the existing prediction.
      try {
        await generateEngagementPrediction(sessionId);
      } catch {
        /* Likely already exists (409) or the session doesn't belong to
           this teacher (404) — either way, try reading the suggestion
           next and let that surface the real error if any. */
      }
      const result = await getAdaptiveSuggestion(sessionId);
      setSuggestion(result);
    } catch (err) {
      setSuggestionError(
        err instanceof NoEngagementPredictionError
          ? "No engagement data available for this session yet."
          : "Couldn't find that session, or it doesn't belong to you."
      );
    } finally {
      setSuggestionLoading(false);
    }
  }

  async function handleAbandonSession() {
    const sessionId = Number(selectedSessionId);
    if (!sessionId) return;

    // First click: show inline confirmation prompt
    if (!abandonConfirming) {
      setAbandonConfirming(true);
      return;
    }

    // Second click: confirmed — proceed
    setAbandonConfirming(false);
    setAbandonMessage(null);
    setSuggestionError(null);
    setAbandonSubmitting(true);
    try {
      await abandonLearningSession(sessionId);
      setAbandonMessage("Session marked as abandoned.");
      refreshSessions();
    } catch (err) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      setSuggestionError(
        status === 409
          ? "This session isn't in progress, so it can't be abandoned."
          : "Couldn't abandon this session. Please try again."
      );
    } finally {
      setAbandonSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-foreground">Analytics</h1>
        <p className="mt-1 text-muted-foreground">
          Engagement and performance insights across your students.
        </p>
      </div>

      {error && <EmptyState icon={BarChart3} title="Something went wrong" description={error} />}

      {/* ── Model Performance (ML diagnostics) ──────────────────────────────
          Global, not per-student: shows how well the engagement-prediction
          ensemble model (Random Forest + Gradient Boosting + Logistic Regression) generalizes, evaluated on a genuine
          held-out 80/20 split rather than reporting training-set accuracy. */}
      {!modelEvalError && (
        <Card variant="glass">
          <CardHeader>
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-primary-500" aria-hidden="true" />
              <CardTitle className="text-base">Engagement Model Performance</CardTitle>
            </div>
            <CardDescription>
              How well the ensemble model predicts engagement, evaluated on
              held-out data it never trained on.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {modelEval === null ? (
              <div className="py-6">
                <LoadingSpinner />
              </div>
            ) : (
              <div className="flex flex-col gap-5">
                {/* Headline stats */}
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                  <div className="rounded-lg border border-border bg-muted p-3 text-center">
                    <p className="text-2xl font-bold text-foreground">
                      {Math.round(modelEval.overall_accuracy * 100)}%
                    </p>
                    <p className="mt-0.5 text-xs text-muted-foreground">Test Accuracy</p>
                  </div>
                  <div className="rounded-lg border border-border bg-muted p-3 text-center">
                    <p className="text-2xl font-bold text-foreground">{modelEval.total_samples}</p>
                    <p className="mt-0.5 text-xs text-muted-foreground">Total Samples</p>
                  </div>
                  <div className="rounded-lg border border-border bg-muted p-3 text-center">
                    <p className="text-2xl font-bold text-foreground">{modelEval.train_samples}</p>
                    <p className="mt-0.5 text-xs text-muted-foreground">Training Samples</p>
                  </div>
                  <div className="rounded-lg border border-border bg-muted p-3 text-center">
                    <p className="text-2xl font-bold text-foreground">{modelEval.test_samples}</p>
                    <p className="mt-0.5 text-xs text-muted-foreground">Held-Out Test Samples</p>
                  </div>
                </div>

                {/* Per-class precision/recall/F1 table */}
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border text-left text-muted-foreground">
                        <th className="py-2 pr-4 font-medium">Engagement Level</th>
                        <th className="py-2 pr-4 font-medium">Precision</th>
                        <th className="py-2 pr-4 font-medium">Recall</th>
                        <th className="py-2 pr-4 font-medium">F1 Score</th>
                        <th className="py-2 font-medium">Test Examples</th>
                      </tr>
                    </thead>
                    <tbody>
                      {modelEval.per_class.map((pc) => (
                        <tr key={pc.label} className="border-b border-border last:border-0">
                          <td className="py-2 pr-4 font-medium text-foreground">{pc.label}</td>
                          <td className="py-2 pr-4 text-foreground">{pc.precision.toFixed(2)}</td>
                          <td className="py-2 pr-4 text-foreground">{pc.recall.toFixed(2)}</td>
                          <td className="py-2 pr-4 text-foreground">{pc.f1_score.toFixed(2)}</td>
                          <td className="py-2 text-muted-foreground">{pc.support}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Confusion matrix as a heatmap-style chart */}
                <div>
                  <p className="mb-2 text-sm font-medium text-foreground">Confusion Matrix</p>
                  <AnalyticsChart
                    ariaLabel="Confusion matrix showing predicted vs actual engagement labels on held-out test data"
                    height={220}
                    data={[
                      {
                        type: "heatmap",
                        z: modelEval.confusion_matrix,
                        x: modelEval.confusion_matrix_labels,
                        y: modelEval.confusion_matrix_labels,
                        colorscale: [
                          [0, "#EFF6FF"],
                          [1, CHART_COLOURS.primary],
                        ],
                        showscale: false,
                        texttemplate: "%{z}",
                        textfont: { size: 14 },
                      },
                    ]}
                    layout={{
                      xaxis: { title: { text: "Predicted" } },
                      yaxis: { title: { text: "Actual" }, autorange: "reversed" },
                    }}
                  />
                </div>

                <p className="text-xs text-muted-foreground leading-relaxed">{modelEval.notes}</p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {!error && students.length === 0 && (
        <EmptyState
          icon={BarChart3}
          title="No analytics data yet"
          description="Add a student to start seeing progress insights."
        />
      )}

      {!error && students.length > 0 && (
        <>
          <div className="flex flex-col gap-1.5 sm:max-w-xs">
            <label htmlFor="analytics-student" className="text-sm font-medium text-foreground">
              Student
            </label>
            <select
              id="analytics-student"
              value={selectedStudentId ?? ""}
              onChange={(e) => setSelectedStudentId(Number(e.target.value))}
              className="h-11 w-full rounded-md border border-border bg-surface px-3 text-base text-foreground focus:border-primary-500 focus:outline-none"
            >
              {students.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.full_name}
                </option>
              ))}
            </select>
          </div>

          {!analytics ? (
            <div className="flex justify-center py-12">
              <LoadingSpinner />
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Card variant="glass">
                <CardHeader>
                  <CardTitle>{analytics.total_sessions}</CardTitle>
                  <CardDescription>Total Sessions</CardDescription>
                </CardHeader>
              </Card>
              <Card variant="glass">
                <CardHeader>
                  <CardTitle>{analytics.sessions_completed}</CardTitle>
                  <CardDescription>Completed</CardDescription>
                </CardHeader>
              </Card>
              <Card variant="glass">
                <CardHeader>
                  <CardTitle>
                    {analytics.average_quiz_score !== null
                      ? `${Math.round(analytics.average_quiz_score)}%`
                      : "—"}
                  </CardTitle>
                  <CardDescription>Average Quiz Score</CardDescription>
                </CardHeader>
              </Card>
              <Card variant="glass">
                <CardHeader>
                  <CardTitle>{analytics.total_engagement_predictions}</CardTitle>
                  <CardDescription>Engagement Predictions</CardDescription>
                </CardHeader>
              </Card>
            </div>
          )}

          {analytics && analytics.total_sessions > 0 && (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <Card variant="glass">
                <CardHeader>
                  <CardTitle className="text-base">Session Status</CardTitle>
                  <CardDescription>How this student's sessions have progressed</CardDescription>
                </CardHeader>
                <CardContent>
                  <AnalyticsChart
                    ariaLabel={`Session status breakdown: ${analytics.sessions_started} in progress, ${analytics.sessions_completed} completed, ${analytics.sessions_abandoned} abandoned`}
                    data={[
                      {
                        type: "bar",
                        orientation: "h",
                        x: [
                          analytics.sessions_completed,
                          analytics.sessions_started,
                          analytics.sessions_abandoned,
                        ],
                        y: ["Completed", "In Progress", "Not Finished"],
                        marker: {
                          color: [
                            CHART_COLOURS.success,
                            CHART_COLOURS.warning,
                            CHART_COLOURS.muted,
                          ],
                        },
                      },
                    ]}
                    layout={{
                      xaxis: { title: { text: "Sessions" }, dtick: 1 },
                    }}
                  />
                </CardContent>
              </Card>

              <Card variant="glass">
                <CardHeader>
                  <CardTitle className="text-base">Engagement Levels</CardTitle>
                  <CardDescription>Predicted engagement across all sessions</CardDescription>
                </CardHeader>
                <CardContent>
                  {Object.keys(analytics.engagement_label_counts).length === 0 ? (
                    <p className="py-8 text-center text-sm text-muted-foreground">
                      No engagement predictions yet.
                    </p>
                  ) : (
                    <AnalyticsChart
                      ariaLabel="Engagement level distribution across sessions"
                      data={[
                        {
                          type: "pie",
                          labels: Object.keys(analytics.engagement_label_counts),
                          values: Object.values(analytics.engagement_label_counts),
                          marker: {
                            colors: Object.keys(analytics.engagement_label_counts).map((label) =>
                              label === "High"
                                ? CHART_COLOURS.success
                                : label === "Medium"
                                ? CHART_COLOURS.warning
                                : CHART_COLOURS.error
                            ),
                          },
                          hole: 0.5,
                          textinfo: "label+percent",
                          textfont: { size: 12 },
                        },
                      ]}
                      layout={{ showlegend: true, legend: { orientation: "h", y: -0.1 } }}
                    />
                  )}
                </CardContent>
              </Card>
            </div>
          )}

          <Card variant="glass">
            <CardHeader>
              <div className="flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-primary-600" />
                <CardTitle>Adaptive Suggestion</CardTitle>
              </div>
              <CardDescription>
                Look up a rule-based, explainable suggestion for a specific learning session.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              {sessions === null ? (
                <div className="flex justify-center py-4">
                  <LoadingSpinner size="sm" />
                </div>
              ) : sessions.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No learning sessions have been assigned yet. Assign one from Learning Plans
                  first.
                </p>
              ) : (
                <form className="flex flex-col gap-3 sm:flex-row sm:items-end" onSubmit={handleGetSuggestion}>
                  <div className="flex flex-1 flex-col gap-1.5">
                    <label htmlFor="suggestion-session" className="text-sm font-medium text-foreground">
                      Learning Session
                    </label>
                    <select
                      id="suggestion-session"
                      required
                      value={selectedSessionId}
                      onChange={(e) => setSelectedSessionId(e.target.value)}
                      className="h-11 w-full rounded-md border border-border bg-surface px-3 text-base text-foreground focus:border-primary-500 focus:outline-none"
                    >
                      <option value="">Choose a session</option>
                      {sessions.map((s) => (
                        <option key={s.id} value={s.id}>
                          {studentName(s.student_id)} — {contentTitle(s.learning_content_id)} (
                          {s.status})
                        </option>
                      ))}
                    </select>
                  </div>
                  <Button type="submit" disabled={suggestionLoading || !selectedSessionId}>
                    Get Suggestion
                  </Button>
                  {abandonConfirming ? (
                    <div className="flex items-center gap-2 rounded-md border border-warning-200 bg-warning-50 px-3 py-2">
                      <span className="text-sm text-warning-700">Mark as abandoned?</span>
                      <Button
                        type="button"
                        variant="destructive"
                        size="sm"
                        disabled={abandonSubmitting}
                        onClick={handleAbandonSession}
                      >
                        {abandonSubmitting ? "..." : "Confirm"}
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => setAbandonConfirming(false)}
                      >
                        Cancel
                      </Button>
                    </div>
                  ) : (
                    <Button
                      type="button"
                      variant="outline"
                      disabled={!selectedSessionId}
                      onClick={handleAbandonSession}
                    >
                      Abandon Session
                    </Button>
                  )}
                </form>
              )}

              {abandonMessage && (
                <p className="text-sm text-success-600">{abandonMessage}</p>
              )}

              {suggestionLoading && <AILoadingState kind="analyzingLearning" />}

              {suggestionError && <p className="text-sm text-error-600">{suggestionError}</p>}

              {suggestion && (
                <div className="rounded-md border border-border bg-muted p-4">
                  <p className="font-medium text-foreground">{suggestion.suggestion}</p>
                  <p className="mt-1 text-sm text-muted-foreground">{suggestion.reasoning}</p>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
