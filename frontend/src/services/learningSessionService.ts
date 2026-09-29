import { apiClient } from "@/services/apiClient";

/** Mirrors schemas/learning_session.py's response shape (teacher-facing create). */
export interface LearningSessionRecord {
  id: number;
  student_id: number;
  learning_plan_id: number;
  learning_content_id: number;
  status: "started" | "completed" | "abandoned";
  difficulty_level_at_session: string;
}

export interface LearningSessionCreatePayload {
  student_id: number;
  learning_plan_id: number;
  learning_content_id: number;
}

export async function listLearningSessions(): Promise<LearningSessionRecord[]> {
  const { data } = await apiClient.get<LearningSessionRecord[]>("/learning-sessions");
  return data;
}

export async function abandonLearningSession(sessionId: number): Promise<LearningSessionRecord> {
  const { data } = await apiClient.post<LearningSessionRecord>(
    `/learning-sessions/${sessionId}/abandon`,
    {}
  );
  return data;
}

export async function assignLearningSession(
  payload: LearningSessionCreatePayload
): Promise<LearningSessionRecord> {
  const { data } = await apiClient.post<LearningSessionRecord>("/learning-sessions", payload);
  return data;
}
