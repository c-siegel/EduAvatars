import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Play, RotateCcw, Volume2 } from "lucide-react";
import { Input, Textarea } from "@/components/Input";
import { Button } from "@/components/Button";
import { Callout } from "@/components/Callout";
import { projectsApi } from "@/api/projects";
import { errorMessage } from "@/api/client";
import { toAbsoluteAvatarUrl } from "@/lib/avatarUrl";
import type { StepProps } from "../types";
import styles from "./Step3Behavior.module.css";

const START_PROMPT_MAX_LENGTH = 1000;

interface Step3Props extends StepProps {
  autoGenerate: boolean;
  onGenerated: () => void;
  projectId: string;
  // Persisted values (not the draft) — the generate-audio endpoint synthesizes the SAVED
  // start_prompt, same posture as Step4Preview's live test chat.
  savedStartPrompt: string;
  startAudioUrl: string | null;
  ttsEnabled: boolean;
}

// Schritt 3 — Verhalten: Zielgruppe, Preprompt (mit generischem Standardtext) und Startnachricht.
export function Step3Behavior({
  draft,
  onChange,
  autoGenerate,
  onGenerated,
  projectId,
  savedStartPrompt,
  startAudioUrl,
  ttsEnabled,
}: Step3Props) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const defaultPreprompt = t("configurator.step3.defaultPreprompt");
  // Holds the currently playing preview so a second click restarts it instead of overlapping.
  const previewAudioRef = useRef<HTMLAudioElement | null>(null);
  // Preprompt is sent to the model as plain text either way — this only toggles how it's shown
  // here, so an educator can check that Markdown they wrote (lists, headings, bold) renders as
  // intended.
  const [prepromptCompiled, setPrepromptCompiled] = useState(false);

  function playAudioPreview() {
    const url = toAbsoluteAvatarUrl(startAudioUrl);
    if (!url) return;
    previewAudioRef.current?.pause();
    const audio = new Audio(url);
    previewAudioRef.current = audio;
    audio.play().catch((error) => console.error("Audio-Vorschau konnte nicht abgespielt werden.", error));
  }

  const generateAudioMutation = useMutation({
    mutationFn: () => projectsApi.generateStartAudio(projectId),
    onSuccess: (updated) => {
      queryClient.setQueryData(["projects", projectId], updated);
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  const startPromptDirty = draft.startPrompt !== savedStartPrompt;
  const canGenerateAudio = Boolean(savedStartPrompt.trim()) && ttsEnabled && !startPromptDirty;

  useEffect(() => {
    if (autoGenerate) {
      onChange({ preprompt: defaultPreprompt });
      onGenerated();
    }
    // Nur beim ersten Betreten von Schritt 3 automatisch befüllen, solange preprompt leer ist.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoGenerate]);

  function resetToDefault() {
    onChange({ preprompt: defaultPreprompt });
  }

  return (
    <div>
      <Input
        label={t("configurator.step3.targetGroup")}
        placeholder={t("configurator.step3.targetGroupPlaceholder")}
        value={draft.gradeLevel}
        onChange={(e) => onChange({ gradeLevel: e.target.value })}
      />

      <div className={styles.toolbar}>
        <div className={styles.viewToggle} role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={!prepromptCompiled}
            className={!prepromptCompiled ? styles.viewToggleActive : undefined}
            onClick={() => setPrepromptCompiled(false)}
          >
            {t("configurator.step3.prepromptRawTab")}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={prepromptCompiled}
            className={prepromptCompiled ? styles.viewToggleActive : undefined}
            onClick={() => setPrepromptCompiled(true)}
          >
            {t("configurator.step3.prepromptCompiledTab")}
          </button>
        </div>
        <Button size="sm" onClick={resetToDefault}>
          <RotateCcw size={14} /> {t("configurator.step3.resetToDefault")}
        </Button>
      </div>
      {prepromptCompiled ? (
        <div className={styles.field}>
          <span className={styles.label}>{t("configurator.step3.preprompt")}</span>
          <div className={styles.markdownPreview}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {draft.preprompt || t("configurator.step3.prepromptCompiledEmpty")}
            </ReactMarkdown>
          </div>
        </div>
      ) : (
        <Textarea
          label={t("configurator.step3.preprompt")}
          value={draft.preprompt}
          onChange={(e) => onChange({ preprompt: e.target.value })}
          rows={12}
        />
      )}
      <p className={styles.hint}>{t("configurator.step3.prepromptMarkdownHint")}</p>
      <p className={styles.hint}>{t("configurator.step3.resetHint")}</p>

      <Textarea
        label={t("configurator.step3.startMessageOptional")}
        hint={`${draft.startPrompt.length} / ${START_PROMPT_MAX_LENGTH}`}
        value={draft.startPrompt}
        onChange={(e) => onChange({ startPrompt: e.target.value.slice(0, START_PROMPT_MAX_LENGTH) })}
        rows={4}
      />
      <p className={styles.hint}>{t("configurator.step3.startMessageHint")}</p>

      <div className={styles.audioSection}>
        {startAudioUrl ? (
          <Callout variant="success">{t("configurator.step3.audioGenerated")}</Callout>
        ) : (
          <p className={styles.hint}>{t("configurator.step3.audioNotGenerated")}</p>
        )}
        {startPromptDirty && <Callout variant="warning">{t("configurator.step3.audioUnsavedHint")}</Callout>}
        {!ttsEnabled && <Callout variant="warning">{t("configurator.step3.audioTtsDisabledHint")}</Callout>}
        {generateAudioMutation.isError && (
          <Callout variant="danger">
            {errorMessage(generateAudioMutation.error, t("configurator.step3.audioGenerateError"))}
          </Callout>
        )}
        <div className={styles.audioButtons}>
          <Button
            size="sm"
            onClick={() => generateAudioMutation.mutate()}
            disabled={!canGenerateAudio || generateAudioMutation.isPending}
          >
            <Volume2 size={14} /> {t("configurator.step3.generateAudio")}
          </Button>
          {startAudioUrl && (
            <Button size="sm" onClick={playAudioPreview}>
              <Play size={14} /> {t("configurator.step3.listenToAudio")}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
