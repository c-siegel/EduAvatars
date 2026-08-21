import { useRef, type ChangeEvent } from "react";
import { Plus, X } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Input, Textarea } from "@/components/Input";
import { Avatar } from "@/components/Avatar";
import { Callout } from "@/components/Callout";
import { avatarLibraryApi, type AvatarModel } from "@/api/avatarLibrary";
import { backgroundLibraryApi, type BackgroundImage } from "@/api/backgroundLibrary";
import { toAbsoluteAvatarUrl } from "@/lib/avatarUrl";
import type { StepProps } from "../types";
import styles from "./Step1Appearance.module.css";
import sharedStyles from "./shared.module.css";

// Schritt 1 — Aussehen: Projektname, Kurzbeschreibung, Avatar-Bibliothek, Hintergrundbild und
// Chat-Sichtbarkeit.
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
      onChange({ avatarModelUrl: avatar.fileUrl });

      // Vorschaubild ist ein reines Extra (Grid zeigt sonst weiter Initialen) — Fehler hier
      // (z.B. kein WebGL) sollen den eigentlichen Upload nicht als fehlgeschlagen erscheinen lassen.
      // Dynamischer Import: three.js/GLTFLoader sollen nicht ins eager geladene Haupt-Bundle des
      // Konfigurators wandern, sondern nur bei einem tatsächlichen Avatar-Upload nachgeladen werden
      // (gleiches Muster wie der dynamische Import von @met4citizen/talkinghead in TalkingHeadAvatar.tsx).
      try {
        const { captureAvatarThumbnail } = await import("@/lib/avatarThumbnail");
        const thumbnail = await captureAvatarThumbnail(toAbsoluteAvatarUrl(avatar.fileUrl)!);
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
      onChange({ avatarBackgroundUrl: background.fileUrl });
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
    // Ausgewählter Avatar wird beim Löschen mit abgewählt, statt im Entwurf auf eine nicht mehr
    // existierende Datei zeigen zu lassen.
    if (draft.avatarModelUrl === avatar.fileUrl) onChange({ avatarModelUrl: null });
    removeAvatarMutation.mutate(avatar.id);
  }

  function handleRemoveBackground(background: BackgroundImage) {
    if (!window.confirm(t("configurator.step1.confirmDeleteLibraryItem", { name: background.name }))) return;
    if (draft.avatarBackgroundUrl === background.fileUrl) onChange({ avatarBackgroundUrl: null });
    removeBackgroundMutation.mutate(background.id);
  }

  const avatars = avatarsQuery.data ?? [];
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
                onClick={() => onChange({ avatarModelUrl: avatar.fileUrl })}
                aria-label={avatar.name}
                aria-pressed={draft.avatarModelUrl === avatar.fileUrl}
              >
                {/* fileUrl zeigt auf die .glb-3D-Datei selbst, kein Bild — die Kachel zeigt stattdessen
                    das einmalig client-seitig gerenderte Vorschaubild (thumbnailUrl), solange keins
                    vorhanden ist (z.B. noch in Erzeugung oder fehlgeschlagen) bleibt es bei Initialen. */}
                <Avatar
                  name={avatar.name}
                  src={toAbsoluteAvatarUrl(avatar.thumbnailUrl)}
                  selected={draft.avatarModelUrl === avatar.fileUrl}
                />
              </button>
              <button
                type="button"
                className={styles.tileDelete}
                onClick={() => handleRemoveAvatar(avatar)}
                aria-label={t("configurator.step1.deleteItem", { name: avatar.name })}
                disabled={removeAvatarMutation.isPending}
              >
                <X size={12} />
              </button>
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
              !draft.avatarBackgroundUrl ? styles.backgroundTileSelected : ""
            }`}
            onClick={() => onChange({ avatarBackgroundUrl: null })}
            aria-label={t("configurator.step1.noBackgroundAriaLabel")}
            aria-pressed={!draft.avatarBackgroundUrl}
          >
            {t("configurator.step1.default")}
          </button>
          {backgrounds.map((background) => (
            <div key={background.id} className={styles.tileWrap}>
              <button
                type="button"
                className={`${styles.backgroundTile} ${
                  draft.avatarBackgroundUrl === background.fileUrl ? styles.backgroundTileSelected : ""
                }`}
                style={{ backgroundImage: `url(${toAbsoluteAvatarUrl(background.fileUrl)})` }}
                onClick={() => onChange({ avatarBackgroundUrl: background.fileUrl })}
                aria-label={background.name}
                aria-pressed={draft.avatarBackgroundUrl === background.fileUrl}
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
      </div>

      <label className={sharedStyles.toggleRow}>
        <input
          type="checkbox"
          checked={draft.chatDefaultOpen}
          onChange={(e) => onChange({ chatDefaultOpen: e.target.checked })}
        />
        <span className={sharedStyles.toggleCopy}>
          <strong>{t("configurator.step1.chatVisibleTitle")}</strong>
          <span>{t("configurator.step1.chatVisibleText")}</span>
        </span>
      </label>
      <Callout variant="info">{t("configurator.step1.chatVisibleNote")}</Callout>
    </>
  );
}
