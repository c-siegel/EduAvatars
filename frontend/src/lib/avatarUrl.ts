import { API_BASE_URL } from "@/api/client";

// Backend liefert avatarUrl router-relativ ohne /api-Präfix (analog avatar-models/{id}/file) —
// für ein direktes <img src> (kein apiClient-Fetch) muss das Präfix hier ergänzt werden.
export function toAbsoluteAvatarUrl(avatarUrl: string | null | undefined): string | undefined {
  return avatarUrl ? `${API_BASE_URL}${avatarUrl}` : undefined;
}
