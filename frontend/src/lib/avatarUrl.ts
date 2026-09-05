import { API_BASE_URL } from "@/api/client";

// Backend liefert avatarUrl router-relativ ohne /api-Präfix (analog avatar-models/{id}/file) —
// für ein direktes <img src> (kein apiClient-Fetch) muss das Präfix hier ergänzt werden.
//
// Exception: the bundled default avatars (Julia, David — see BUILTIN_AVATARS in
// Step1Appearance.tsx) live under the frontend's own public/avatars/ folder, not behind the
// backend API, so their URLs must reach the browser unprefixed.
export function toAbsoluteAvatarUrl(avatarUrl: string | null | undefined): string | undefined {
  if (!avatarUrl) return undefined;
  return avatarUrl.startsWith("/avatars/") ? avatarUrl : `${API_BASE_URL}${avatarUrl}`;
}
