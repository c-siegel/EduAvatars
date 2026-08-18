import { apiClient } from "./client";

export interface BackgroundImage {
  id: string;
  name: string;
  fileUrl: string;
  createdAt: string;
}

export const backgroundLibraryApi = {
  list: () => apiClient.get<BackgroundImage[]>("/backgrounds"),
  upload: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiClient.upload<BackgroundImage>("/backgrounds", formData);
  },
  remove: (backgroundId: string) => apiClient.delete<void>(`/backgrounds/${backgroundId}`),
};
