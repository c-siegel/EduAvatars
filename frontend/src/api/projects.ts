import { apiClient, API_BASE_URL, ApiError, filenameFromContentDisposition } from "./client";
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
  // Also deletes the project's saved conversations and access logs, server-side.
  remove: (id: string) => apiClient.delete<void>(`/projects/${id}`),
  publish: (id: string) => apiClient.post<Project>(`/projects/${id}/publish`),
  unpublish: (id: string) => apiClient.post<Project>(`/projects/${id}/unpublish`),
  // Synthesizes and stores the project's startPrompt as audio (once) — see the "Generate audio"
  // button in Step3Behavior.
  generateStartAudio: (id: string) => apiClient.post<Project>(`/projects/${id}/start-audio`),
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
  // Downloads a project's configuration as a .yml file — bypasses apiClient like
  // analyticsApi.exportConversations, since the response is a file, not JSON.
  exportYaml: async (id: string, fallbackFilename: string) => {
    const res = await fetch(`${API_BASE_URL}/projects/${id}/export`, { credentials: "include" });
    if (!res.ok) throw new ApiError(res.status, await res.text());
    const filename = filenameFromContentDisposition(res.headers.get("Content-Disposition"), fallbackFilename);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  },
  // Creates a new draft project from a previously exported .yml file.
  importYaml: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiClient.upload<Project>("/projects/import", formData);
  },
};
