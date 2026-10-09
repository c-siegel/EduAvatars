import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Play, RotateCcw, Volume2 } from "lucide-react";
import { Input, Textarea } from "@/components/Input";
import { Button } from "@/components/Button";
import { Callout } from "@/components/Callout";
import { LabelWithInfo } from "@/components/InfoTip";
import { projectsApi } from "@/api/projects";
import { errorMessage } from "@/api/client";
import type { Project } from "@/types/project";
import type { StepProps } from "../types";
import { KnowledgeSection } from "./KnowledgeSection";
import styles from "./Step3Behavior.module.css";

const START_PROMPT_MAX_LENGTH = 1000;

interface Step3Props extends StepProps {
  autoGenerate: boolean;
  onGenerated: () => void;
  projectId: string;
  // Persisted value (not the draft) — the generate-audio endpoint synthesizes the SAVED
  // start_prompt, so an audio file only matches the draft while the two are equal.
  savedStartPrompt: string;
  startAudioUrl: string | null;
  hasUnsavedChanges: boolean;
  /** Persists the current draft — "Generate audio" calls this first, so it always speaks what's in
   * the form (same pattern as Step5Publish). */
  onSaveDraft: () => Promise<Project>;
}

// Step 3 — behaviour: target audience, preprompt (with a generic default text), start message and
// the knowledge bases the avatar may draw on.
export function Step3Behavior({
  draft,
  onChange,
  autoGenerate,
  onGenerated,
  projectId,
  savedStartPrompt,
  startAudioUrl,
  hasUnsavedChanges,
  onSaveDraft,
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
    const url = startAudioUrl;
    if (!url) return;
    previewAudioRef.current?.pause();
    const audio = new Audio(url);
    previewAudioRef.current = audio;
    audio.play().catch((error) => console.error("Audio-Vorschau konnte nicht abgespielt werden.", error));
  }

  const generateAudioMutation = useMutation({
    mutationFn: async () => {
      // Saving a changed start message (or voice) also discards the old audio server-side, see
      // backend features/projects/service.py::_START_AUDIO_INVALIDATING_FIELDS.
      if (hasUnsavedChanges) {
        await onSaveDraft();
      }
      return projectsApi.generateStartAudio(projectId);
    },
    onSuccess: (updated) => {
      queryClient.setQueryData(["projects", projectId], updated);
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  // Checked against the draft: generating saves it first.
  const canGenerateAudio = Boolean(draft.startPrompt.trim()) && draft.ttsEnabled;
  // An existing audio file still speaks the saved text — once the draft differs it's outdated
  // (and gets discarded by the save that generating starts with).
  const audioUpToDate = Boolean(startAudioUrl) && draft.startPrompt === savedStartPrompt;

  useEffect(() => {
    if (autoGenerate) {
      onChange({ preprompt: defaultPreprompt });
      onGenerated();
    }
    // Only prefill automatically on the first visit to step 3, while preprompt is empty.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoGenerate]);

  function resetToDefault() {
    onChange({ preprompt: defaultPreprompt });
  }

  const prepromptInfo = (
    <>
      <p className={styles.infoParagraph}>{t("configurator.step3.prepromptMarkdownHint")}</p>
      <p className={styles.infoParagraph}>{t("configurator.step3.resetHint")}</p>
    </>
  );

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
          <LabelWithInfo label={t("configurator.step3.preprompt")} className={styles.label} info={prepromptInfo} />
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
          info={prepromptInfo}
        />
      )}

      <Textarea
        label={t("configurator.step3.startMessageOptional")}
        hint={`${draft.startPrompt.length} / ${START_PROMPT_MAX_LENGTH}`}
        value={draft.startPrompt}
        onChange={(e) => onChange({ startPrompt: e.target.value.slice(0, START_PROMPT_MAX_LENGTH) })}
        rows={4}
        info={t("configurator.step3.startMessageHint")}
      />

      <div className={styles.audioSection}>
        {audioUpToDate ? (
          <Callout variant="success">{t("configurator.step3.audioGenerated")}</Callout>
        ) : (
          <p className={styles.hint}>
            {startAudioUrl ? t("configurator.step3.audioOutdated") : t("configurator.step3.audioNotGenerated")}
          </p>
        )}
        {!draft.ttsEnabled && <Callout variant="warning">{t("configurator.step3.audioTtsDisabledHint")}</Callout>}
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
            <Volume2 size={14} />{" "}
            {hasUnsavedChanges ? t("configurator.step3.saveAndGenerateAudio") : t("configurator.step3.generateAudio")}
          </Button>
          {audioUpToDate && (
            <Button size="sm" onClick={playAudioPreview}>
              <Play size={14} /> {t("configurator.step3.listenToAudio")}
            </Button>
          )}
        </div>
      </div>

      <KnowledgeSection draft={draft} onChange={onChange} />
    </div>
  );
}
