import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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
  { id: 1, label: "Aussehen" },
  { id: 2, label: "Technik" },
  { id: 3, label: "Verhalten" },
  { id: 4, label: "Vorschau" },
  { id: 5, label: "Veröffentlichung" },
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
    creativity: project.creativity,
    saveConversations: project.saveConversations,
    surveyBeforeUrl: project.surveyBeforeUrl ?? "",
    surveyBeforeEnabled: project.surveyBeforeEnabled,
    surveyAfterUrl: project.surveyAfterUrl ?? "",
    surveyAfterEnabled: project.surveyAfterEnabled,
    spokenLanguage: project.spokenLanguage,
    ttsEnabled: project.ttsEnabled,
    ttsApiKeyId: project.ttsApiKeyId,
    ttsVoice: project.ttsVoice ?? "",
    sttEnabled: project.sttEnabled,
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
    draft.creativity !== project.creativity ||
    draft.saveConversations !== project.saveConversations ||
    draft.surveyBeforeUrl !== (project.surveyBeforeUrl ?? "") ||
    draft.surveyBeforeEnabled !== project.surveyBeforeEnabled ||
    draft.surveyAfterUrl !== (project.surveyAfterUrl ?? "") ||
    draft.surveyAfterEnabled !== project.surveyAfterEnabled ||
    draft.spokenLanguage !== project.spokenLanguage ||
    draft.ttsEnabled !== project.ttsEnabled ||
    draft.ttsApiKeyId !== project.ttsApiKeyId ||
    draft.ttsVoice !== (project.ttsVoice ?? "") ||
    draft.sttEnabled !== project.sttEnabled
  );
}

// Screen 1e — Tab Konfigurator: 5-Schritte-Assistent (Aussehen → Technik → Verhalten → Vorschau →
// Veröffentlichung). Abweichung von der einspaltigen Wireframe-Referenz auf ausdrücklichen Wunsch.
export function ConfiguratorPage() {
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
        creativity: data.creativity,
        saveConversations: data.saveConversations,
        surveyBeforeUrl: data.surveyBeforeUrl,
        surveyBeforeEnabled: data.surveyBeforeEnabled,
        surveyAfterUrl: data.surveyAfterUrl,
        surveyAfterEnabled: data.surveyAfterEnabled,
        spokenLanguage: data.spokenLanguage,
        ttsEnabled: data.ttsEnabled,
        ttsApiKeyId: data.ttsApiKeyId,
        ttsVoice: data.ttsVoice || null,
        sttEnabled: data.sttEnabled,
      }),
    onSuccess: (updated) => {
      queryClient.setQueryData(["projects", projectId], updated);
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      toast.show("Fortschritt gespeichert.");
    },
  });

  if (projectQuery.isLoading || !draft) {
    return <p>Lädt …</p>;
  }

  if (projectQuery.isError || !projectQuery.data) {
    return <Callout variant="danger">Projekt konnte nicht geladen werden.</Callout>;
  }

  const project = projectQuery.data;

  function updateDraft(patch: Partial<ConfiguratorDraft>) {
    setDraft((current) => (current ? { ...current, ...patch } : current));
  }

  return (
    <div className={styles.page}>
      <div className={styles.topbar}>
        <div className={styles.titleGroup}>
          <h2 className={styles.title}>{draft.title || "Neues Projekt"}</h2>
          <Badge variant={project.published ? "accent" : "default"}>
            {project.published ? "Publiziert" : "Entwurf · nicht veröffentlicht"}
          </Badge>
        </div>
        <Button variant="accent" onClick={() => saveMutation.mutate(draft)} disabled={saveMutation.isPending}>
          Speichern
        </Button>
      </div>

      {saveMutation.isError && <Callout variant="danger">Speichern fehlgeschlagen. Bitte erneut versuchen.</Callout>}

      <nav className={styles.stepper} aria-label="Konfigurator-Schritte">
        {STEPS.map((s) => (
          <button
            key={s.id}
            type="button"
            className={`${styles.step} ${step === s.id ? styles.stepActive : ""}`}
            onClick={() => setStep(s.id)}
          >
            <span className={styles.stepNumber}>{s.id}</span>
            {s.label}
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
          <Step5Publish draft={draft} onChange={updateDraft} project={project} projectId={projectId} />
        )}
      </div>

      <div className={styles.stepNav}>
        <span>
          {step > 1 && (
            <Button onClick={() => setStep((s) => (s - 1) as StepId)}>Zurück</Button>
          )}
        </span>
        {step < 5 && (
          <Button variant="accent" onClick={() => setStep((s) => (s + 1) as StepId)}>
            Weiter
          </Button>
        )}
      </div>

      {toast.message && <Toast message={toast.message} onDismiss={toast.dismiss} />}
    </div>
  );
}
