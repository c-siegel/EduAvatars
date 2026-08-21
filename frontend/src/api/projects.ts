import { apiClient } from "./client";
import i18n from "@/i18n";
import type { ChatMessage } from "@/types/chat";
import type { Project, ProjectStats } from "@/types/project";

export const projectsApi = {
  list: () => apiClient.get<Project[]>("/projects"),
  stats: () => apiClient.get<ProjectStats>("/projects/stats"),
  create: () => apiClient.post<Project>("/projects", { title: i18n.t("configurator.newProject") }),
  get: (id: string) => apiClient.get<Project>(`/projects/${id}`),
  // chatPassword isn't part of Project (write-only, see types/project.ts) — null clears/disables
  // the chat password, a non-empty string sets/changes it, omitted leaves it unchanged.
  update: (id: string, data: Partial<Project> & { chatPassword?: string | null }) =>
    apiClient.put<Project>(`/projects/${id}`, data),
  publish: (id: string) => apiClient.post<Project>(`/projects/${id}/publish`),
  unpublish: (id: string) => apiClient.post<Project>(`/projects/${id}/unpublish`),
  previewMessage: (id: string, message: string, history: ChatMessage[]) =>
    apiClient.post<{ reply: string; audioBase64: string | null; contentType: string | null }>(
      `/projects/${id}/preview-message`,
      { message, history },
    ),
  transcribe: (id: string, audio: Blob) => {
    const formData = new FormData();
    formData.append("audio", audio, "recording.webm");
    return apiClient.upload<{ text: string }>(`/projects/${id}/transcribe`, formData);
  },
};
