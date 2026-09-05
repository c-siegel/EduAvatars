import { apiClient } from "./client";
import type { User } from "@/types/user";

export const authApi = {
  login: (email: string, password: string) => apiClient.post<User>("/auth/login", { email, password }),
  register: (name: string, email: string, password: string) =>
    apiClient.post<User>("/auth/register", { name, email, password }),
  logout: () => apiClient.post<void>("/auth/logout"),
  me: () => apiClient.get<User>("/auth/me"),
  forgotPassword: (email: string) => apiClient.post<void>("/auth/forgot-password", { email }),
  resetPassword: (token: string, newPassword: string) =>
    apiClient.post<void>("/auth/reset-password", { token, newPassword }),
  registrationStatus: () => apiClient.get<{ enabled: boolean }>("/auth/registration-status"),
};
