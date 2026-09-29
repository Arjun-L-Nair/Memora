import { apiClient } from "@/services/apiClient";

/**
 * studentLearningService.ts
 *
 * Wraps the student-facing /student-learning endpoints
 * (app/api/v1/student_learning.py). Mirrors the backend response
 * shapes directly rather than re-declaring parallel types — these are
 * loose (not code-generated) but kept in exact field-for-field sync
 * with the frozen Pydantic schemas.
 */

export interface LearningSession {
  id: number;
  student_id: number;
  learning_plan_id: number;
  learning_content_id: number;
  started_at: string;
  completed_at: string | null;
  time_spent_seconds: number | null;
  idle_time_seconds: number | null;
  hint_usage_count: number;
  retry_count: number;
  status: "started" | "completed" | "abandoned";
  difficulty_level_at_session: string;
}

export interface LearningContent {
  id: number;
  title: string;
  subject: string | null;
  body: string;
  difficulty_level: string;
  learning_plan_id: number;
  is_active: boolean;
  video_url: string | null;
  teacher_notes: string | null;
}

export interface RecommendedContent {
  learning_plan_id: number;
  content: LearningContent | null;
  reasoning: string;
}

export interface SessionEndMetrics {
  time_spent_seconds?: number;
  idle_time_seconds?: number;
  hint_usage_count?: number;
  retry_count?: number;
}

export async function getTodaysLearning(): Promise<LearningSession[]> {
  const { data } = await apiClient.get<LearningSession[]>("/student-learning/today");
  return data;
}

export async function getAllSessions(): Promise<LearningSession[]> {
  const { data } = await apiClient.get<LearningSession[]>("/student-learning/sessions");
  return data;
}

export async function getSessionById(sessionId: number): Promise<LearningSession | undefined> {
  const sessions = await getAllSessions();
  return sessions.find((s) => s.id === sessionId);
}

/**
 * Get the exact learning content tied to a specific session — not a
 * re-derived recommendation. Use this to display "Today's Lesson" for
 * a session that already exists; the content was chosen once by the
 * teacher when the session was created and should not change.
 */
export async function getContentForSession(sessionId: number): Promise<LearningContent> {
  const { data } = await apiClient.get<LearningContent>(
    `/student-learning/sessions/${sessionId}/content`
  );
  return data;
}

export async function getRecommendedContent(
  learningPlanId: number
): Promise<RecommendedContent> {
  const { data } = await apiClient.get<RecommendedContent>(
    `/student-learning/plans/${learningPlanId}/recommended-content`
  );
  return data;
}

export async function abandonSession(sessionId: number): Promise<LearningSession> {
  const { data } = await apiClient.post<LearningSession>(
    `/student-learning/sessions/${sessionId}/abandon`,
    {}
  );
  return data;
}

export async function completeSession(
  sessionId: number,
  metrics: SessionEndMetrics = {}
): Promise<LearningSession> {
  const { data } = await apiClient.post<LearningSession>(
    `/student-learning/sessions/${sessionId}/complete`,
    metrics
  );
  return data;
}
