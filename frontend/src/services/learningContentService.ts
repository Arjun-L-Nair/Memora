import { apiClient } from "@/services/apiClient";

/** Mirrors schemas/learning_content.py's response/request shapes. */
export interface LearningContentRecord {
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

export interface LearningContentCreatePayload {
  title: string;
  body: string;
  difficulty_level: string;
  learning_plan_id: number;
  video_url?: string | null;
  teacher_notes?: string | null;
}

export interface LearningContentUpdatePayload {
  title?: string;
  body?: string;
  difficulty_level?: string;
  video_url?: string | null;
  teacher_notes?: string | null;
}

export async function updateLearningContent(
  contentId: number,
  payload: LearningContentUpdatePayload
): Promise<LearningContentRecord> {
  const { data } = await apiClient.patch<LearningContentRecord>(
    `/learning-content/${contentId}`,
    payload
  );
  return data;
}

export async function deactivateLearningContent(contentId: number): Promise<LearningContentRecord> {
  const { data } = await apiClient.post<LearningContentRecord>(
    `/learning-content/${contentId}/deactivate`
  );
  return data;
}

export async function listAllLearningContent(): Promise<LearningContentRecord[]> {
  const { data } = await apiClient.get<LearningContentRecord[]>("/learning-content");
  return data;
}

export async function listLearningContentForPlan(
  learningPlanId: number
): Promise<LearningContentRecord[]> {
  const { data } = await apiClient.get<LearningContentRecord[]>(
    `/learning-content?learning_plan_id=${learningPlanId}`
  );
  return data;
}

export async function createLearningContent(
  payload: LearningContentCreatePayload
): Promise<LearningContentRecord> {
  const { data } = await apiClient.post<LearningContentRecord>("/learning-content", payload);
  return data;
}
