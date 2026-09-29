import { apiClient } from "@/services/apiClient";

/** Mirrors schemas/sensory_profile.py's response shape. */
export interface SensoryProfile {
  student_id: number;
  preferred_mode: "visual" | "auditory" | "text" | "mixed";
  sensory_sensitivity_score: number;
  reduce_motion: boolean;
  high_contrast: boolean;
  mute_sounds: boolean;
  font_preference: "default" | "opendyslexic";
  attention_span_minutes: number;
}

export type SensoryProfileUpdate = Partial<Omit<SensoryProfile, "student_id">>;

export async function getSensoryProfile(): Promise<SensoryProfile> {
  const { data } = await apiClient.get<SensoryProfile>("/sensory-profile");
  return data;
}

export async function updateSensoryProfile(
  update: SensoryProfileUpdate
): Promise<SensoryProfile> {
  const { data } = await apiClient.put<SensoryProfile>("/sensory-profile", update);
  return data;
}
