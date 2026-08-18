import { apiClient } from "./client";
import type { ChatMessage } from "@/types/chat";
import type { SpokenLanguage } from "@/types/project";

export interface PublicProject {
  title: string;
  teacherName: string;
  // Erste Nachricht des Avatars, dem Modell ebenfalls als Kontext mitgegeben (siehe Backend
  // services/llm_service.py::send_chat_message). Leer = generische Begrüßung im Frontend.
  startPrompt: string | null;
  avatarModelUrl: string | null;
  avatarBackgroundUrl: string | null;
  spokenLanguage: SpokenLanguage;
  ttsEnabled: boolean;
  sttEnabled: boolean;
  // Siehe types/project.ts — noch ohne UI-Auswirkung auf dieser Seite.
  chatDefaultOpen: boolean;
  surveyBeforeUrl: string | null;
  surveyAfterUrl: string | null;
}

export const publicChatApi = {
  loadTutor: (slug: string) => apiClient.get<PublicProject>(`/public/${slug}`),
  // Backend gibt {reply} zurück, keine vollständige Conversation (siehe app/api/public_chat.py) —
  // war zuvor fälschlich als Conversation typisiert.
  sendMessage: (slug: string, message: string, history: ChatMessage[]) =>
    // llmMs/ttsMs: backend-side call durations, only meaningful together with the client-side
    // timestamps captured in PublicChat/index.tsx's latency-test log (?latencyTest=1).
    apiClient.post<{
      reply: string;
      audioBase64: string | null;
      contentType: string | null;
      llmMs: number | null;
      ttsMs: number | null;
    }>(`/public/${slug}/message`, { message, history }),
  transcribe: (slug: string, audio: Blob) => {
    const formData = new FormData();
    formData.append("audio", audio, "recording.webm");
    return apiClient.upload<{ text: string; sttMs: number | null }>(`/public/${slug}/transcribe`, formData);
  },
};
