import { apiClient } from "@/services/apiClient";

/**
 * reflectionService.ts
 *
 * Wraps the student-facing /learning-reflections endpoints
 * (app/api/v1/learning_reflection.py). Mirrors
 * schemas/learning_reflection.py's response shape.
 */

export interface LearningReflection {
  id: number;
  learning_session_id: number;
  content: string;
  generated_by: string;
  generated_at: string;
}

/** Thrown when a reflection already exists for this session (409). */
export class ReflectionAlreadyExistsError extends Error {}

/**
 * Look up an already-existing reflection for this session, if any,
 * without trying to generate one. Returns null when no reflection has
 * been generated yet — a normal state, not an error. Callers should
 * try this first and only fall back to generateReflection() when it
 * returns null, so revisiting Reflection after it's already been
 * generated shows the existing one instead of a dead-end 409.
 */
export async function getReflectionBySession(
  learningSessionId: number
): Promise<LearningReflection | null> {
  const { data } = await apiClient.get<LearningReflection | null>(
    `/learning-reflections/by-session/${learningSessionId}`
  );
  return data;
}

export async function generateReflection(learningSessionId: number): Promise<LearningReflection> {
  try {
    const { data } = await apiClient.post<LearningReflection>(
      `/learning-reflections/generate/${learningSessionId}`
    );
    return data;
  } catch (error) {
    if (isConflict(error)) {
      throw new ReflectionAlreadyExistsError(
        "A reflection already exists for this session."
      );
    }
    throw error;
  }
}

function isConflict(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "response" in error &&
    (error as { response?: { status?: number } }).response?.status === 409
  );
}
