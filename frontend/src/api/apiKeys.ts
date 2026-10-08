import { apiClient } from "./client";
import type { ApiKey, ApiKeyInput, ProviderSpec } from "@/types/apiKey";
import type { SttServerEngine } from "@/types/project";

export const apiKeysApi = {
  listProviders: () => apiClient.get<ProviderSpec[]>("/providers"),
  localTtsStatus: () => apiClient.get<{ available: boolean }>("/providers/local-tts-status"),
  browserSttStatus: () => apiClient.get<{ available: boolean }>("/providers/browser-stt-status"),
  serverSttStatus: () =>
    apiClient.get<{ defaultEngine: SttServerEngine; parakeetAvailable: boolean }>("/providers/server-stt-status"),
  list: () => apiClient.get<ApiKey[]>("/api-keys"),
  create: (input: ApiKeyInput) => apiClient.post<ApiKey>("/api-keys", input),
  // Keys are addressed by their id (no longer by provider) — the same teacher can store several
  // keys for the same provider.
  update: (id: string, input: ApiKeyInput) => apiClient.put<ApiKey>(`/api-keys/${id}`, input),
  remove: (id: string) => apiClient.delete<void>(`/api-keys/${id}`),
  test: (id: string) => apiClient.post<{ status: string; message: string | null }>(`/api-keys/${id}/test`),
};
