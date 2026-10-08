import { apiClient } from "./client";

export interface AvatarModel {
  id: string;
  name: string;
  fileUrl: string;
  thumbnailUrl: string | null;
  createdAt: string;
}

export const avatarLibraryApi = {
  list: () => apiClient.get<AvatarModel[]>("/avatars"),
  upload: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiClient.upload<AvatarModel>("/avatars", formData);
  },
  // PNG rendered once on the client (see lib/avatarThumbnail.ts) — not a user upload.
  uploadThumbnail: (avatarId: string, thumbnail: Blob) => {
    const formData = new FormData();
    formData.append("file", thumbnail, "thumbnail.png");
    return apiClient.upload<AvatarModel>(`/avatars/${avatarId}/thumbnail`, formData);
  },
  remove: (avatarId: string) => apiClient.delete<void>(`/avatars/${avatarId}`),
};
