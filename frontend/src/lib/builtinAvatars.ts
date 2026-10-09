import type { AvatarModel } from "@/api/avatarLibrary";

// Bundled under frontend/public/avatars/ (see ATTRIBUTION.md there) instead of coming from the
// user's own upload library — shown in every project's avatar grid so a project always has a
// usable face without requiring an upload first. Not real AvatarModel rows (no DB id; their
// thumbnails are static PNGs next to the .glb files), so the "builtin-" id prefix marks them. A
// project stores one of these by name (builtinAvatar, the part after "builtin-").
export const BUILTIN_AVATARS: AvatarModel[] = [
  { id: "builtin-julia", name: "Julia", fileUrl: "/avatars/julia.glb", thumbnailUrl: "/avatars/julia.png", createdAt: "" },
  { id: "builtin-david", name: "David", fileUrl: "/avatars/david.glb", thumbnailUrl: "/avatars/david.png", createdAt: "" },
];

export function isBuiltinAvatar(avatar: AvatarModel): boolean {
  return avatar.id.startsWith("builtin-");
}
