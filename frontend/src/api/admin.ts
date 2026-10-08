// API client for the /admin/* backend routes: account management (list/create/promote/demote/
// enable/disable/reset-password) and the instance-wide site settings, all admin-only.
import { apiClient } from "./client";

export interface AdminUser {
  id: string;
  name: string;
  email: string;
  school: string | null;
  isAdmin: boolean;
  enabled: boolean;
  mustChangePassword: boolean;
  createdAt: string;
}

export interface SiteSettings {
  contactEmail: string | null;
  contactPhone: string | null;
  providerName: string | null;
  providerStreet: string | null;
  providerCity: string | null;
  providerCountry: string | null;
  registrationEnabled: boolean;
  // 0 = keep saved student conversations forever.
  conversationRetentionDays: number;
  // Knowledge-base (RAG) limits; the first three can't exceed KnowledgeCeilings.
  ragMaxUploadMb: number;
  ragMaxPages: number;
  ragMaxCharsPerDocument: number;
  ragMaxDocumentsPerKb: number;
  ragMaxKbPerUser: number;
  ragUserQuotaMb: number;
  ragUploadRatePer10Min: number;
}

// The operator's ceilings for the knowledge limits (RAG_HARD_MAX_* in the knowledge service).
export interface KnowledgeCeilings {
  enabled: boolean;
  maxUploadMb: number;
  maxPages: number;
  maxChars: number;
}

export const adminApi = {
  listUsers: () => apiClient.get<AdminUser[]>("/admin/users"),
  createUser: (name: string, email: string, password: string, isAdmin: boolean) =>
    apiClient.post<AdminUser>("/admin/users", { name, email, password, isAdmin }),
  updateUser: (userId: string, data: { isAdmin?: boolean; enabled?: boolean }) =>
    apiClient.put<AdminUser>(`/admin/users/${userId}`, data),
  resetPassword: (userId: string, newPassword: string) =>
    apiClient.post<void>(`/admin/users/${userId}/reset-password`, { newPassword }),
  getSettings: () => apiClient.get<SiteSettings>("/admin/settings"),
  updateSettings: (data: Partial<SiteSettings>) => apiClient.put<SiteSettings>("/admin/settings", data),
  getKnowledgeCeilings: () => apiClient.get<KnowledgeCeilings>("/admin/settings/knowledge-ceilings"),
};
