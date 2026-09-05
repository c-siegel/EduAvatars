import { apiClient } from "./client";

export interface AvatarModel {
  id: string;
  name: string;
  fileUrl: string;
  thumbnailUrl: string | null;
  createdAt: string;
}

export const avatarLibraryApi = {
  list: () => apiClient.get<AvatarModel[]>("/avatar-models"),
  upload: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiClient.upload<AvatarModel>("/avatar-models", formData);
  },
  // Einmalig client-seitig gerendertes PNG (siehe lib/avatarThumbnail.ts) — kein Nutzer-Upload.
  uploadThumbnail: (avatarId: string, thumbnail: Blob) => {
    const formData = new FormData();
    formData.append("file", thumbnail, "thumbnail.png");
    return apiClient.upload<AvatarModel>(`/avatar-models/${avatarId}/thumbnail`, formData);
  },
  remove: (avatarId: string) => apiClient.delete<void>(`/avatar-models/${avatarId}`),
};
