import { apiClient } from "@/services/apiClient";

/** Mirrors schemas/analytics.py's StudentAnalyticsResponse. */
export interface StudentAnalytics {
  student_id: number;
  total_sessions: number;
  sessions_started: number;
  sessions_completed: number;
  sessions_abandoned: number;
  total_quiz_attempts: number;
  quizzes_submitted: number;
  average_quiz_score: number | null;
  total_engagement_predictions: number;
  engagement_label_counts: Record<string, number>;
}

export interface PerClassMetrics {
  label: string;
  precision: number;
  recall: number;
  f1_score: number;
  support: number;
}

export interface ModelEvaluation {
  total_samples: number;
  train_samples: number;
  test_samples: number;
  overall_accuracy: number;
  per_class: PerClassMetrics[];
  confusion_matrix: number[][];
  confusion_matrix_labels: string[];
  notes: string;
}

export async function getModelEvaluation(): Promise<ModelEvaluation> {
  const { data } = await apiClient.get<ModelEvaluation>(
    "/engagement-predictions/model/evaluation"
  );
  return data;
}

export async function getStudentAnalytics(studentId: number): Promise<StudentAnalytics> {
  const { data } = await apiClient.get<StudentAnalytics>(`/analytics/students/${studentId}`);
  return data;
}
