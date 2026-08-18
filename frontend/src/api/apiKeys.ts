import { apiClient } from "./client";
import type { ApiKey, ApiKeyInput, ProviderSpec } from "@/types/apiKey";

export const apiKeysApi = {
  listProviders: () => apiClient.get<ProviderSpec[]>("/api-keys/providers"),
  list: () => apiClient.get<ApiKey[]>("/api-keys"),
  create: (input: ApiKeyInput) => apiClient.post<ApiKey>("/api-keys", input),
  // Keys werden über ihre id adressiert (nicht mehr über den Provider) — dieselbe Lehrkraft kann
  // mehrere Schlüssel desselben Anbieters hinterlegen.
  update: (id: string, input: ApiKeyInput) => apiClient.put<ApiKey>(`/api-keys/${id}`, input),
  remove: (id: string) => apiClient.delete<void>(`/api-keys/${id}`),
  test: (id: string) => apiClient.post<{ status: string; message: string | null }>(`/api-keys/${id}/test`),
};
