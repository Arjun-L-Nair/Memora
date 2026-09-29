import { apiClient } from "@/services/apiClient";

export interface SkillSummary {
  id: number;
  name: string;
  description: string;
  tier: "Easy" | "Medium" | "Hard";
  category: string;
  unlocked: boolean;
  passed: boolean;
}

export interface SkillExercise {
  id: number;
  prompt: string;
  options: string[];
}

export interface SkillExercisesResponse {
  skill_id: number;
  skill_name: string;
  exercises: SkillExercise[];
}

export interface SkillAttemptResult {
  is_correct: boolean;
  correct_option_index: number;
  skill_passed: boolean;
}

export interface TeacherSkillProgressEntry {
  id: number;
  name: string;
  tier: "Easy" | "Medium" | "Hard";
  passed: boolean;
}

export async function listSkills(): Promise<SkillSummary[]> {
  const { data } = await apiClient.get<SkillSummary[]>("/skills");
  return data;
}

export async function getSkillExercises(skillId: number): Promise<SkillExercisesResponse> {
  const { data } = await apiClient.get<SkillExercisesResponse>(`/skills/${skillId}/exercises`);
  return data;
}

export async function submitSkillAttempt(
  skillId: number,
  skillExerciseId: number,
  selectedOptionIndex: number
): Promise<SkillAttemptResult> {
  const { data } = await apiClient.post<SkillAttemptResult>(`/skills/${skillId}/attempts`, {
    skill_exercise_id: skillExerciseId,
    selected_option_index: selectedOptionIndex,
  });
  return data;
}

export async function getStudentSkillProgress(studentId: number): Promise<TeacherSkillProgressEntry[]> {
  const { data } = await apiClient.get<{ student_id: number; skills: TeacherSkillProgressEntry[] }>(
    `/skills/progress/${studentId}`
  );
  return data.skills;
}
