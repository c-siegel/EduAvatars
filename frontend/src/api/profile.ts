import { apiClient } from "./client";
import type { User } from "@/types/user";

export const profileApi = {
  update: (data: Partial<User>) => apiClient.put<User>("/profile", data),
  changePassword: (currentPassword: string, newPassword: string) =>
    apiClient.put<void>("/profile/password", { currentPassword, newPassword }),
  deleteAccount: () => apiClient.delete<void>("/profile"),
  logoutEverywhere: () => apiClient.post<void>("/profile/logout-everywhere"),
  uploadPicture: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiClient.upload<User>("/profile/picture", formData);
  },
  deletePicture: () => apiClient.delete<User>("/profile/picture"),
};
