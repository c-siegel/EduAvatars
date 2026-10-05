import { apiClient } from "./client";
import type { User } from "@/types/user";

export const profileApi = {
  update: (data: Partial<User>) => apiClient.put<User>("/me", data),
  changePassword: (currentPassword: string, newPassword: string) =>
    apiClient.put<void>("/me/password", { currentPassword, newPassword }),
  deleteAccount: () => apiClient.delete<void>("/me"),
  logoutEverywhere: () => apiClient.post<void>("/me/logout-everywhere"),
  uploadPicture: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiClient.upload<User>("/me/picture", formData);
  },
  deletePicture: () => apiClient.delete<User>("/me/picture"),
};
