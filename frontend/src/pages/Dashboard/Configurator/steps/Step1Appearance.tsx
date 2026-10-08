import { useRef, type ChangeEvent } from "react";
import { Plus, X } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Input, Textarea } from "@/components/Input";
import { Avatar } from "@/components/Avatar";
import { Callout } from "@/components/Callout";
import { errorMessage } from "@/api/client";
import { avatarLibraryApi, type AvatarModel } from "@/api/avatarLibrary";
import { backgroundLibraryApi, type BackgroundImage } from "@/api/backgroundLibrary";
import { CHAT_LAYOUTS } from "@/types/project";
import type { ConfiguratorDraft, StepProps } from "../types";
import styles from "./Step1Appearance.module.css";
import sharedStyles from "./shared.module.css";

// Bundled under frontend/public/avatars/ (see ATTRIBUTION.md there) instead of coming from the
// user's own upload library — shown in every project's avatar grid below so a project always has
// a usable face without requiring an upload first. Not real AvatarModel rows (no DB id; their
// thumbnails are static PNGs next to the .glb files), so isBuiltinAvatar() below keys off the "builtin-" id prefix to skip the delete
// button and the removeAvatarMutation call, which only work on the user's own library entries. A
// project stores one of these by name (builtinAvatar, the part after "builtin-"), see avatarRef().
const BUILTIN_AVATARS: AvatarModel[] = [
  { id: "builtin-julia", name: "Julia", fileUrl: "/avatars/julia.glb", thumbnailUrl: "/avatars/julia.png", createdAt: "" },
  { id: "builtin-david", name: "David", fileUrl: "/avatars/david.glb", thumbnailUrl: "/avatars/david.png", createdAt: "" },
];

function isBuiltinAvatar(avatar: AvatarModel): boolean {
  return avatar.id.startsWith("builtin-");
}

// The draft fields that select `avatar` — exactly one of the two references is set.
function avatarRef(avatar: AvatarModel): Pick<ConfiguratorDraft, "avatarModelId" | "builtinAvatar"> {
  return isBuiltinAvatar(avatar)
    ? { avatarModelId: null, builtinAvatar: avatar.id.slice("builtin-".length) }
    : { avatarModelId: avatar.id, builtinAvatar: null };
}

function isSelectedAvatar(draft: ConfiguratorDraft, avatar: AvatarModel): boolean {
  const ref = avatarRef(avatar);
  return draft.avatarModelId === ref.avatarModelId && draft.builtinAvatar === ref.builtinAvatar;
}

// Step 1 — appearance: project name, short description, avatar library, background image and
// chat visibility.
export function Step1Appearance({ draft, onChange }: StepProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const backgroundFileInputRef = useRef<HTMLInputElement>(null);
  const avatarsQuery = useQuery({ queryKey: ["avatar-models"], queryFn: avatarLibraryApi.list });
  const backgroundsQuery = useQuery({ queryKey: ["backgrounds"], queryFn: backgroundLibraryApi.list });

  const uploadMutation = useMutation({
    mutationFn: avatarLibraryApi.upload,
    onSuccess: async (avatar) => {
      queryClient.invalidateQueries({ queryKey: ["avatar-models"] });
      onChange(avatarRef(avatar));

      // The thumbnail is purely a bonus (the grid otherwise keeps showing initials) — errors here
      // (e.g. no WebGL) must not make the actual upload look failed.
      // Dynamic import: three.js/GLTFLoader shouldn't end up in the configurator's eagerly loaded
      // main bundle, only be loaded when an avatar is actually uploaded (same pattern as the
      // dynamic import of @met4citizen/talkinghead in TalkingHeadAvatar.tsx).
      try {
        const { captureAvatarThumbnail } = await import("@/lib/avatarThumbnail");
        const thumbnail = await captureAvatarThumbnail(avatar.fileUrl);
        await avatarLibraryApi.uploadThumbnail(avatar.id, thumbnail);
        queryClient.invalidateQueries({ queryKey: ["avatar-models"] });
      } catch (error) {
        console.error("Avatar-Vorschaubild konnte nicht erzeugt werden.", error);
      }
    },
  });

  const uploadBackgroundMutation = useMutation({
    mutationFn: backgroundLibraryApi.upload,
    onSuccess: (background) => {
      queryClient.invalidateQueries({ queryKey: ["backgrounds"] });
      onChange({ avatarBackgroundId: background.id });
    },
  });

  const removeAvatarMutation = useMutation({
    mutationFn: avatarLibraryApi.remove,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["avatar-models"] }),
  });

  const removeBackgroundMutation = useMutation({
    mutationFn: backgroundLibraryApi.remove,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["backgrounds"] }),
  });

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) uploadMutation.mutate(file);
    event.target.value = "";
  }

  function handleBackgroundFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) uploadBackgroundMutation.mutate(file);
    event.target.value = "";
  }

  function handleRemoveAvatar(avatar: AvatarModel) {
    if (!window.confirm(t("configurator.step1.confirmDeleteLibraryItem", { name: avatar.name }))) return;
    // The selected avatar is deselected on delete too, instead of leaving the draft pointing at a
    // file that no longer exists.
    if (isSelectedAvatar(draft, avatar)) onChange({ avatarModelId: null, builtinAvatar: null });
    removeAvatarMutation.mutate(avatar.id);
  }

  function handleRemoveBackground(background: BackgroundImage) {
    if (!window.confirm(t("configurator.step1.confirmDeleteLibraryItem", { name: background.name }))) return;
    if (draft.avatarBackgroundId === background.id) onChange({ avatarBackgroundId: null });
    removeBackgroundMutation.mutate(background.id);
  }

  const avatars = [...BUILTIN_AVATARS, ...(avatarsQuery.data ?? [])];
  const backgrounds = backgroundsQuery.data ?? [];

  return (
    <>
      <Input
        label={t("configurator.step1.projectName")}
        value={draft.title}
        onChange={(e) => onChange({ title: e.target.value })}
        required
      />

      <Textarea
        label={t("configurator.step1.descriptionOptional")}
        placeholder={t("configurator.step1.descriptionPlaceholder")}
        value={draft.description}
        onChange={(e) => onChange({ description: e.target.value })}
        rows={2}
      />

      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <h3>{t("configurator.step1.avatarLibrary")}</h3>
          <span className={styles.count}>{t("configurator.step1.available", { count: avatars.length })}</span>
        </div>
        <div className={styles.avatarGrid}>
          {avatars.map((avatar) => (
            <div key={avatar.id} className={styles.tileWrap}>
              <button
                type="button"
                className={styles.avatarButton}
                onClick={() => onChange(avatarRef(avatar))}
                aria-label={avatar.name}
                aria-pressed={isSelectedAvatar(draft, avatar)}
              >
                {/* fileUrl points at the .glb 3D file itself, not an image — the tile shows the
                    preview image rendered once on the client (thumbnailUrl) instead; while there
                    is none (e.g. still being generated, or failed) it stays at initials. */}
                <Avatar
                  name={avatar.name}
                  src={avatar.thumbnailUrl ?? undefined}
                  selected={isSelectedAvatar(draft, avatar)}
                />
              </button>
              {!isBuiltinAvatar(avatar) && (
                <button
                  type="button"
                  className={styles.tileDelete}
                  onClick={() => handleRemoveAvatar(avatar)}
                  aria-label={t("configurator.step1.deleteItem", { name: avatar.name })}
                  disabled={removeAvatarMutation.isPending}
                >
                  <X size={12} />
                </button>
              )}
            </div>
          ))}
          <button
            type="button"
            className={styles.uploadTile}
            onClick={() => fileInputRef.current?.click()}
            aria-label={t("configurator.step1.uploadAvatar")}
            disabled={uploadMutation.isPending}
          >
            <Plus size={18} />
          </button>
          <input ref={fileInputRef} type="file" accept=".glb,model/gltf-binary" hidden onChange={handleFileChange} />
        </div>
        {(uploadMutation.isError || removeAvatarMutation.isError) && (
          <Callout variant="danger">
            {errorMessage(uploadMutation.error ?? removeAvatarMutation.error, t("configurator.step1.avatarActionError"))}
          </Callout>
        )}
      </div>

      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <h3>{t("configurator.step1.backgroundImage")}</h3>
          <span className={styles.count}>{t("configurator.step1.available", { count: backgrounds.length })}</span>
        </div>
        <div className={styles.backgroundGrid}>
          <button
            type="button"
            className={`${styles.backgroundTile} ${styles.backgroundNone} ${
              !draft.avatarBackgroundId ? styles.backgroundTileSelected : ""
            }`}
            onClick={() => onChange({ avatarBackgroundId: null })}
            aria-label={t("configurator.step1.noBackgroundAriaLabel")}
            aria-pressed={!draft.avatarBackgroundId}
          >
            {t("configurator.step1.default")}
          </button>
          {backgrounds.map((background) => (
            <div key={background.id} className={styles.tileWrap}>
              <button
                type="button"
                className={`${styles.backgroundTile} ${
                  draft.avatarBackgroundId === background.id ? styles.backgroundTileSelected : ""
                }`}
                style={{ backgroundImage: `url(${background.fileUrl})` }}
                onClick={() => onChange({ avatarBackgroundId: background.id })}
                aria-label={background.name}
                aria-pressed={draft.avatarBackgroundId === background.id}
              />
              <button
                type="button"
                className={styles.tileDelete}
                onClick={() => handleRemoveBackground(background)}
                aria-label={t("configurator.step1.deleteItem", { name: background.name })}
                disabled={removeBackgroundMutation.isPending}
              >
                <X size={12} />
              </button>
            </div>
          ))}
          <button
            type="button"
            className={styles.backgroundUploadTile}
            onClick={() => backgroundFileInputRef.current?.click()}
            aria-label={t("configurator.step1.uploadBackground")}
            disabled={uploadBackgroundMutation.isPending}
          >
            <Plus size={18} />
          </button>
          <input
            ref={backgroundFileInputRef}
            type="file"
            accept=".png,.jpg,.jpeg,image/png,image/jpeg"
            hidden
            onChange={handleBackgroundFileChange}
          />
        </div>
        {(uploadBackgroundMutation.isError || removeBackgroundMutation.isError) && (
          <Callout variant="danger">
            {errorMessage(
              uploadBackgroundMutation.error ?? removeBackgroundMutation.error,
              t("configurator.step1.backgroundActionError"),
            )}
          </Callout>
        )}
      </div>

      <fieldset className={sharedStyles.radioGroup}>
        <legend className={sharedStyles.label}>{t("configurator.step1.chatLayoutTitle")}</legend>
        {CHAT_LAYOUTS.map((layout) => (
          <label key={layout} className={sharedStyles.toggleRow}>
            <input
              type="radio"
              name="chat-layout"
              checked={draft.chatLayout === layout}
              onChange={() => onChange({ chatLayout: layout })}
            />
            <span className={sharedStyles.toggleCopy}>
              <strong>{t(`configurator.step1.chatLayouts.${layout}.title`)}</strong>
              <span>{t(`configurator.step1.chatLayouts.${layout}.text`)}</span>
            </span>
          </label>
        ))}
      </fieldset>
      {/* Without voice in and out there'd be no way to talk to an avatar without a chat — the public
          page then falls back to avatar + chat (see effectiveChatLayout in pages/PublicChat). */}
      {draft.chatLayout === "avatar_only" && !(draft.ttsEnabled && draft.sttEnabled) && (
        <Callout variant="warning">{t("configurator.step1.avatarOnlyNeedsVoice")}</Callout>
      )}
    </>
  );
}
