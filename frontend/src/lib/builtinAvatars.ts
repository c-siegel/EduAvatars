import type { AvatarModel } from "@/api/avatarLibrary";
import type { Project } from "@/types/project";

// Bundled under frontend/public/avatars/ (see ATTRIBUTION.md there) instead of coming from the
// user's own upload library — shown in every project's avatar grid so a project always has a
// usable face without requiring an upload first. Not real AvatarModel rows (no DB id; their
// thumbnails are static PNGs next to the .glb files), so the "builtin-" id prefix marks them. A
// project stores one of these by name (builtinAvatar, the part after "builtin-").
export const BUILTIN_AVATARS: AvatarModel[] = [
  { id: "builtin-julia", name: "Julia", fileUrl: "/avatars/julia.glb", thumbnailUrl: "/avatars/julia.png", createdAt: "" },
  { id: "builtin-david", name: "David", fileUrl: "/avatars/david.glb", thumbnailUrl: "/avatars/david.png", createdAt: "" },
];

// What the chat falls back to when a project has neither a library nor a built-in avatar (see
// DEFAULT_AVATAR_URL in components/TalkingHeadAvatar).
const DEFAULT_BUILTIN_AVATAR = BUILTIN_AVATARS[0];

export function isBuiltinAvatar(avatar: AvatarModel): boolean {
  return avatar.id.startsWith("builtin-");
}

/** The library thumbnail of the face students see for this project, or null where there's none
 * (a chat-only project, or a library avatar whose thumbnail hasn't been rendered). */
export function projectAvatarThumbnailUrl(
  project: Pick<Project, "avatarModelId" | "builtinAvatar" | "chatLayout">,
  libraryAvatars: AvatarModel[] | undefined,
): string | null {
  if (project.chatLayout === "chat_only") return null;
  if (project.avatarModelId) {
    return libraryAvatars?.find((avatar) => avatar.id === project.avatarModelId)?.thumbnailUrl ?? null;
  }
  const builtin = project.builtinAvatar
    ? BUILTIN_AVATARS.find((avatar) => avatar.id === `builtin-${project.builtinAvatar}`)
    : DEFAULT_BUILTIN_AVATAR;
  return builtin?.thumbnailUrl ?? null;
}
