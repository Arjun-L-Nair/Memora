import { apiClient } from "@/services/apiClient";

/** Mirrors schemas/learning_plan.py's response shape. */
export interface LearningPlanRecord {
  id: number;
  title: string;
  description: string | null;
  student_id: number | null; // legacy — see backend LearningPlan.student_id docstring
  teacher_id: number;
  estimated_duration_minutes: number | null;
  is_active: boolean;
  assigned_student_ids: number[];
}

export interface LearningPlanCreatePayload {
  title: string;
  description?: string;
  /** Optional now — omit to create a reusable, unassigned plan and
   * assign it to students afterward via assignPlanToStudents(). */
  student_id?: number;
  estimated_duration_minutes?: number;
}

export async function listLearningPlans(): Promise<LearningPlanRecord[]> {
  const { data } = await apiClient.get<LearningPlanRecord[]>("/learning-plans");
  return data;
}

export async function getLearningPlan(planId: number): Promise<LearningPlanRecord> {
  const { data } = await apiClient.get<LearningPlanRecord>(`/learning-plans/${planId}`);
  return data;
}

export async function createLearningPlan(
  payload: LearningPlanCreatePayload
): Promise<LearningPlanRecord> {
  const { data } = await apiClient.post<LearningPlanRecord>("/learning-plans", payload);
  return data;
}

export interface LearningPlanUpdatePayload {
  title?: string;
  description?: string;
  estimated_duration_minutes?: number;
}

export async function updateLearningPlan(
  planId: number,
  payload: LearningPlanUpdatePayload
): Promise<LearningPlanRecord> {
  const { data } = await apiClient.patch<LearningPlanRecord>(`/learning-plans/${planId}`, payload);
  return data;
}

export async function deactivateLearningPlan(planId: number): Promise<LearningPlanRecord> {
  const { data } = await apiClient.post<LearningPlanRecord>(
    `/learning-plans/${planId}/deactivate`
  );
  return data;
}

/** Assign a plan to one or more students from the teacher's roster.
 * Already-assigned students are silently skipped — safe to re-submit
 * a full roster selection without computing a diff yourself. */
export async function assignPlanToStudents(
  planId: number,
  studentIds: number[]
): Promise<LearningPlanRecord> {
  const { data } = await apiClient.post<LearningPlanRecord>(`/learning-plans/${planId}/assign`, {
    student_ids: studentIds,
  });
  return data;
}

export async function unassignPlanFromStudent(
  planId: number,
  studentId: number
): Promise<LearningPlanRecord> {
  const { data } = await apiClient.delete<LearningPlanRecord>(
    `/learning-plans/${planId}/assign/${studentId}`
  );
  return data;
}
