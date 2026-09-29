import { apiClient } from "@/services/apiClient";

/** Mirrors schemas/learning_companion.py's response shape. */
export interface CompanionMessage {
  message: string;
  generated_by: "gemini" | "ollama" | "template";
  detected_emotion: string | null;
}

export type InteractionMode = "chat" | "social_story" | "visual_schedule" | "calm_down";

export interface ConversationTurn {
  role: "student" | "mira";
  message: string;
  emotion_detected: string | null;
  created_at: string;
}

export async function askCompanion(
  studentMessage?: string,
  interactionMode: InteractionMode = "chat"
): Promise<CompanionMessage> {
  const { data } = await apiClient.post<CompanionMessage>("/learning-companion/message", {
    student_message: studentMessage || undefined,
    interaction_mode: interactionMode,
  });
  return data;
}

export async function getCompanionHistory(): Promise<ConversationTurn[]> {
  const { data } = await apiClient.get<{ turns: ConversationTurn[] }>("/learning-companion/history");
  return data.turns;
}
