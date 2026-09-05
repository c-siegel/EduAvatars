import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/Button";
import { Badge } from "@/components/Badge";
import { Callout } from "@/components/Callout";
import { Toast } from "@/components/Toast";
import { useToast } from "@/hooks/useToast";
import { projectsApi } from "@/api/projects";
import type { Project } from "@/types/project";
import { Step1Appearance } from "./steps/Step1Appearance";
import { Step2Technical } from "./steps/Step2Technical";
import { Step3Behavior } from "./steps/Step3Behavior";
import { Step4Preview } from "./steps/Step4Preview";
import { Step5Publish } from "./steps/Step5Publish";
import type { ConfiguratorDraft } from "./types";
import styles from "./Configurator.module.css";

const STEPS = [
  { id: 1, labelKey: "configurator.steps.appearance" },
  { id: 2, labelKey: "configurator.steps.technical" },
  { id: 3, labelKey: "configurator.steps.behavior" },
  { id: 4, labelKey: "configurator.steps.preview" },
  { id: 5, labelKey: "configurator.steps.publish" },
] as const;

type StepId = (typeof STEPS)[number]["id"];

function toDraft(project: Project): ConfiguratorDraft {
  return {
    title: project.title,
    description: project.description ?? "",
    avatarModelUrl: project.avatarModelUrl,
    avatarBackgroundUrl: project.avatarBackgroundUrl,
    chatDefaultOpen: project.chatDefaultOpen,
    gradeLevel: project.gradeLevel ?? "",
    preprompt: project.preprompt ?? "",
    startPrompt: project.startPrompt ?? "",
    // Keine Vorauswahl mehr: das Dropdown in Schritt 3 listet nur eingerichtete Schlüssel, und
    // solange keiner gewählt wurde, zeigt es einen Platzhalter statt eines Modells, das die
    // Lehrkraft gar nicht bestätigt hat.
    llmApiKeyId: project.llmApiKeyId,
    temperature: project.temperature,
    topP: project.topP,
    saveConversations: project.saveConversations,
    requireVisitorName: project.requireVisitorName,
    surveyBeforeUrl: project.surveyBeforeUrl ?? "",
    surveyBeforeEnabled: project.surveyBeforeEnabled,
    surveyAfterUrl: project.surveyAfterUrl ?? "",
    surveyAfterEnabled: project.surveyAfterEnabled,
    spokenLanguage: project.spokenLanguage,
    ttsEnabled: project.ttsEnabled,
    ttsApiKeyId: project.ttsApiKeyId,
    ttsVoice: project.ttsVoice ?? "",
    sttApiKeyId: project.sttApiKeyId,
    sttEnabled: project.sttEnabled,
    streamingEnabled: project.streamingEnabled,
  };
}

// Vergleicht nur die tatsächlich persistierten Felder (goal/personality sind rein Schritt-1-lokal,
// siehe types.ts) — bestimmt, ob der "ungespeicherte Änderungen"-Hinweis in Schritt 4 erscheint.
function isDirty(draft: ConfiguratorDraft, project: Project): boolean {
  return (
    draft.title !== project.title ||
    draft.description !== (project.description ?? "") ||
    draft.avatarModelUrl !== project.avatarModelUrl ||
    draft.avatarBackgroundUrl !== project.avatarBackgroundUrl ||
    draft.chatDefaultOpen !== project.chatDefaultOpen ||
    (draft.gradeLevel || null) !== project.gradeLevel ||
    draft.preprompt !== (project.preprompt ?? "") ||
    draft.startPrompt !== (project.startPrompt ?? "") ||
    draft.llmApiKeyId !== project.llmApiKeyId ||
    draft.temperature !== project.temperature ||
    draft.topP !== project.topP ||
    draft.saveConversations !== project.saveConversations ||
    draft.requireVisitorName !== project.requireVisitorName ||
    draft.surveyBeforeUrl !== (project.surveyBeforeUrl ?? "") ||
    draft.surveyBeforeEnabled !== project.surveyBeforeEnabled ||
    draft.surveyAfterUrl !== (project.surveyAfterUrl ?? "") ||
    draft.surveyAfterEnabled !== project.surveyAfterEnabled ||
    draft.spokenLanguage !== project.spokenLanguage ||
    draft.ttsEnabled !== project.ttsEnabled ||
    draft.ttsApiKeyId !== project.ttsApiKeyId ||
    draft.ttsVoice !== (project.ttsVoice ?? "") ||
    draft.sttApiKeyId !== project.sttApiKeyId ||
    draft.sttEnabled !== project.sttEnabled ||
    draft.streamingEnabled !== project.streamingEnabled
  );
}

// Screen 1e — Tab Konfigurator: 5-Schritte-Assistent (Aussehen → Technik → Verhalten → Vorschau →
// Veröffentlichung). Abweichung von der einspaltigen Wireframe-Referenz auf ausdrücklichen Wunsch.
export function ConfiguratorPage() {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const projectId = id!;
  const queryClient = useQueryClient();
  const toast = useToast();

  const projectQuery = useQuery({
    queryKey: ["projects", projectId],
    queryFn: () => projectsApi.get(projectId),
  });

  const [step, setStep] = useState<StepId>(1);
  const [draft, setDraft] = useState<ConfiguratorDraft | null>(null);
  const [prepromptGenerated, setPrepromptGenerated] = useState(false);

  // Entwurf einmalig aus den geladenen Projektdaten initialisieren.
  useEffect(() => {
    if (projectQuery.data && !draft) {
      setDraft(toDraft(projectQuery.data));
      setPrepromptGenerated(Boolean(projectQuery.data.preprompt));
    }
  }, [projectQuery.data, draft]);

  const saveMutation = useMutation({
    mutationFn: (data: ConfiguratorDraft) =>
      projectsApi.update(projectId, {
        title: data.title,
        description: data.description,
        avatarModelUrl: data.avatarModelUrl,
        avatarBackgroundUrl: data.avatarBackgroundUrl,
        chatDefaultOpen: data.chatDefaultOpen,
        gradeLevel: data.gradeLevel || null,
        preprompt: data.preprompt,
        startPrompt: data.startPrompt,
        llmApiKeyId: data.llmApiKeyId,
        temperature: data.temperature,
        topP: data.topP,
        saveConversations: data.saveConversations,
        requireVisitorName: data.requireVisitorName,
        surveyBeforeUrl: data.surveyBeforeUrl,
        surveyBeforeEnabled: data.surveyBeforeEnabled,
        surveyAfterUrl: data.surveyAfterUrl,
        surveyAfterEnabled: data.surveyAfterEnabled,
        spokenLanguage: data.spokenLanguage,
        ttsEnabled: data.ttsEnabled,
        ttsApiKeyId: data.ttsApiKeyId,
        ttsVoice: data.ttsVoice || null,
        sttApiKeyId: data.sttApiKeyId,
        sttEnabled: data.sttEnabled,
        streamingEnabled: data.streamingEnabled,
      }),
    onSuccess: (updated) => {
      queryClient.setQueryData(["projects", projectId], updated);
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      toast.show(t("configurator.progressSaved"));
    },
  });

  if (projectQuery.isLoading || !draft) {
    return <p>{t("common.loading")}</p>;
  }

  if (projectQuery.isError || !projectQuery.data) {
    return <Callout variant="danger">{t("configurator.loadError")}</Callout>;
  }

  const project = projectQuery.data;

  function updateDraft(patch: Partial<ConfiguratorDraft>) {
    setDraft((current) => (current ? { ...current, ...patch } : current));
  }

  return (
    <div className={styles.page}>
      <div className={styles.topbar}>
        <div className={styles.titleGroup}>
          <h2 className={styles.title}>{draft.title || t("configurator.newProject")}</h2>
          <Badge variant={project.published ? "accent" : "default"}>
            {project.published ? t("overview.card.published") : t("configurator.draftUnpublished")}
          </Badge>
        </div>
        <Button variant="accent" onClick={() => saveMutation.mutate(draft)} disabled={saveMutation.isPending}>
          {t("common.save")}
        </Button>
      </div>

      {saveMutation.isError && <Callout variant="danger">{t("configurator.saveError")}</Callout>}

      <nav className={styles.stepper} aria-label={t("configurator.stepsAriaLabel")}>
        {STEPS.map((s) => (
          <button
            key={s.id}
            type="button"
            className={`${styles.step} ${step === s.id ? styles.stepActive : ""}`}
            onClick={() => setStep(s.id)}
          >
            <span className={styles.stepNumber}>{s.id}</span>
            {t(s.labelKey)}
          </button>
        ))}
      </nav>

      <div className={styles.stepContent}>
        {step === 1 && <Step1Appearance draft={draft} onChange={updateDraft} />}
        {step === 2 && <Step2Technical draft={draft} onChange={updateDraft} />}
        {step === 3 && (
          <Step3Behavior
            draft={draft}
            onChange={updateDraft}
            autoGenerate={!prepromptGenerated}
            onGenerated={() => setPrepromptGenerated(true)}
            projectId={projectId}
            savedStartPrompt={project.startPrompt ?? ""}
            startAudioUrl={project.startAudioUrl}
            ttsEnabled={project.ttsEnabled}
          />
        )}
        {step === 4 && (
          // avatarModelUrl/ttsEnabled kommen bewusst von project (gespeicherter Stand), nicht vom
          // draft — die preview-message-Route arbeitet serverseitig auch auf den persistierten
          // Projektdaten (siehe Kommentar in Step4Preview.tsx).
          <Step4Preview
            projectId={projectId}
            title={draft.title}
            startPrompt={project.startPrompt}
            avatarModelUrl={project.avatarModelUrl}
            avatarBackgroundUrl={project.avatarBackgroundUrl}
            ttsEnabled={project.ttsEnabled}
            hasUnsavedChanges={isDirty(draft, project)}
          />
        )}
        {step === 5 && (
          <Step5Publish
            draft={draft}
            onChange={updateDraft}
            project={project}
            projectId={projectId}
            hasUnsavedChanges={isDirty(draft, project)}
            onSaveDraft={() => saveMutation.mutateAsync(draft)}
          />
        )}
      </div>

      <div className={styles.stepNav}>
        <span>
          {step > 1 && <Button onClick={() => setStep((s) => (s - 1) as StepId)}>{t("common.back")}</Button>}
        </span>
        {step < 5 && (
          <Button variant="accent" onClick={() => setStep((s) => (s + 1) as StepId)}>
            {t("configurator.next")}
          </Button>
        )}
      </div>

      {toast.message && <Toast message={toast.message} onDismiss={toast.dismiss} />}
    </div>
  );
}
