import { apiClient } from "@/services/apiClient";

/** Mirrors schemas/early_warning.py's AtRiskStudentEntry. */
export interface AtRiskStudent {
  student_id: number;
  student_name: string;
  risk_score: number;
  risk_level: string;
  contributing_factors: string[];
}

export interface StudentRisk {
  student_id: number;
  risk_score: number;
  risk_level: string;
  contributing_factors: string[];
}

export async function getAtRiskStudents(riskThreshold = 50): Promise<AtRiskStudent[]> {
  const { data } = await apiClient.get<{ students: AtRiskStudent[] }>("/early-warning/at-risk", {
    params: { risk_threshold: riskThreshold },
  });
  return data.students;
}

export async function getStudentRisk(studentId: number): Promise<StudentRisk> {
  const { data } = await apiClient.get<StudentRisk>(`/early-warning/students/${studentId}`);
  return data;
}
