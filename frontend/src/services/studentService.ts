import { apiClient } from "@/services/apiClient";

/** Mirrors schemas/student.py's response/request shapes. */
export interface StudentRecord {
  id: number;
  student_code: string;
  full_name: string;
  teacher_id: number;
  current_difficulty_level: string;
  is_active: boolean;
}

export interface StudentCreatePayload {
  student_code: string;
  full_name: string;
  pin: string;
}

export async function listStudents(): Promise<StudentRecord[]> {
  const { data } = await apiClient.get<StudentRecord[]>("/students");
  return data;
}

export async function createStudent(payload: StudentCreatePayload): Promise<StudentRecord> {
  const { data } = await apiClient.post<StudentRecord>("/students", payload);
  return data;
}

export interface StudentUpdatePayload {
  full_name?: string;
  student_code?: string;
}

export async function updateStudent(
  studentId: number,
  payload: StudentUpdatePayload
): Promise<StudentRecord> {
  const { data } = await apiClient.patch<StudentRecord>(`/students/${studentId}`, payload);
  return data;
}

export async function resetStudentPin(studentId: number, pin: string): Promise<StudentRecord> {
  const { data } = await apiClient.post<StudentRecord>(`/students/${studentId}/reset-pin`, {
    pin,
  });
  return data;
}

export async function deactivateStudent(studentId: number): Promise<StudentRecord> {
  const { data } = await apiClient.post<StudentRecord>(`/students/${studentId}/deactivate`);
  return data;
}
