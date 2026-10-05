// API client for the /voice-clips/* backend routes: a teacher's private library of voice clips
// that local text-to-speech clones a project's voice from.

import { API_BASE_URL, ApiError, apiClient } from "./client";
import type { SpokenLanguage } from "@/types/project";

export interface VoiceClip {
  id: string;
  name: string;
  // Owner-only route (sent with the session cookie), usable directly as an <audio> src.
  fileUrl: string;
  durationSeconds: number;
  consentConfirmedAt: string;
  createdAt: string;
}

export const voiceClipsApi = {
  list: () => apiClient.get<VoiceClip[]>("/voice-clips"),
  // `consent` is the uploader's confirmation that they may use this voice — the backend refuses
  // the upload without it.
  upload: (name: string, audio: Blob, filename: string, consent: boolean) => {
    const formData = new FormData();
    formData.append("file", audio, filename);
    formData.append("name", name);
    formData.append("consent", String(consent));
    return apiClient.upload<VoiceClip>("/voice-clips", formData);
  },
  remove: (id: string) => apiClient.delete<void>(`/voice-clips/${id}`),
  // Returns audio, not JSON, so it can't go through apiClient. Can take over a minute when the
  // local TTS service has to load its model first.
  preview: async (id: string, text: string, language: SpokenLanguage): Promise<Blob> => {
    const res = await fetch(`${API_BASE_URL}/voice-clips/${id}/preview`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, language }),
    });
    if (!res.ok) throw new ApiError(res.status, await res.text());
    return res.blob();
  },
};
