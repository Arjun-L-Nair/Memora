import { apiClient } from "@/services/apiClient";

/** Mirrors schemas/admin.py's TeacherAdminResponse. */
export interface TeacherRecord {
  id: number;
  full_name: string;
  email: string;
  organization_name: string | null;
  is_active: boolean;
}

export interface TeacherCreatePayload {
  full_name: string;
  email: string;
  password: string;
  organization_name?: string;
}

/** Mirrors schemas/student.py's StudentResponse (reused as-is by the admin router). */
export interface AdminStudentRecord {
  id: number;
  student_code: string;
  full_name: string;
  teacher_id: number;
  current_difficulty_level: string;
  is_active: boolean;
}

/** Mirrors schemas/admin.py's SystemStatisticsResponse. */
export interface SystemStatistics {
  total_teachers: number;
  active_teachers: number;
  inactive_teachers: number;
  total_students: number;
  active_students: number;
  inactive_students: number;
  total_learning_sessions: number;
  total_quiz_attempts: number;
}

export async function listTeachers(): Promise<TeacherRecord[]> {
  const { data } = await apiClient.get<TeacherRecord[]>("/admin/teachers");
  return data;
}

export async function createTeacher(payload: TeacherCreatePayload): Promise<TeacherRecord> {
  const { data } = await apiClient.post<TeacherRecord>("/admin/teachers", payload);
  return data;
}

export async function deactivateTeacher(teacherId: number): Promise<TeacherRecord> {
  const { data } = await apiClient.post<TeacherRecord>(`/admin/teachers/${teacherId}/deactivate`);
  return data;
}

export async function activateTeacher(teacherId: number): Promise<TeacherRecord> {
  const { data } = await apiClient.post<TeacherRecord>(`/admin/teachers/${teacherId}/activate`);
  return data;
}

export async function listAllStudents(): Promise<AdminStudentRecord[]> {
  const { data } = await apiClient.get<AdminStudentRecord[]>("/admin/students");
  return data;
}

export async function getSystemStatistics(): Promise<SystemStatistics> {
  const { data } = await apiClient.get<SystemStatistics>("/admin/stats");
  return data;
}

export interface SeedDemoDataResult {
  already_seeded: boolean;
  output: string;
}

/**
 * Trigger the synthetic demonstration dataset seed script (6 students,
 * learning plans, varied content, sessions, quiz attempts, reflections,
 * and engagement predictions). Idempotent — safe to call even if demo
 * data already exists; the backend detects this and does nothing.
 *
 * Takes noticeably longer than a typical API call (the backend runs
 * the seed script as a subprocess that itself makes ~150+ HTTP calls
 * against the running server) — callers should show a loading state
 * with a "this may take up to a minute" message rather than assuming
 * a fast response.
 */
export async function seedDemoData(): Promise<SeedDemoDataResult> {
  const { data } = await apiClient.post<SeedDemoDataResult>(
    "/admin/seed-demo-data",
    {},
    { timeout: 120000 } // matches the backend's own subprocess timeout
  );
  return data;
}
