import { apiClient } from "@/services/apiClient";

/** Mirrors schemas/engagement_prediction.py's response shape. */
export interface EngagementPrediction {
  id: number;
  learning_session_id: number;
  quiz_accuracy: number | null;
  time_spent_seconds: number | null;
  idle_time_seconds: number | null;
  hint_usage_count: number | null;
  retry_count: number | null;
  engagement_score: number;
  engagement_label: string;
  explanation: string | null;
  predicted_at: string;
}

/** Mirrors schemas/adaptive_suggestion.py's AdaptiveSuggestionResponse. */
export interface AdaptiveSuggestion {
  learning_session_id: number;
  suggestion: string;
  reasoning: string;
  based_on_engagement_label: string;
  based_on_engagement_score: number;
}

export class NoEngagementPredictionError extends Error {}

export async function generateEngagementPrediction(
  learningSessionId: number
): Promise<EngagementPrediction> {
  const { data } = await apiClient.post<EngagementPrediction>(
    `/engagement-predictions/${learningSessionId}/generate`
  );
  return data;
}

export async function getAdaptiveSuggestion(
  learningSessionId: number
): Promise<AdaptiveSuggestion> {
  try {
    const { data } = await apiClient.get<AdaptiveSuggestion>(
      `/engagement-predictions/${learningSessionId}/adaptive-suggestion`
    );
    return data;
  } catch (error) {
    if (
      typeof error === "object" &&
      error !== null &&
      "response" in error &&
      (error as { response?: { status?: number } }).response?.status === 404
    ) {
      throw new NoEngagementPredictionError(
        "No engagement prediction exists yet for this session."
      );
    }
    throw error;
  }
}
