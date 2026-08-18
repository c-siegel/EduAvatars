import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Copy } from "lucide-react";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Callout } from "@/components/Callout";
import { Input } from "@/components/Input";
import { projectsApi } from "@/api/projects";
import type { Project } from "@/types/project";
import type { StepProps } from "../types";
import styles from "./shared.module.css";

interface Step5Props extends StepProps {
  project: Project;
  projectId: string;
}

// Schritt 5 — Veröffentlichung: Aufzeichnung, Umfragen und das eigentliche Publizieren.
// Checkbox und URL der Umfragen sind bewusst getrennte Felder: eine URL kann stehen bleiben,
// während die Umfrage vorübergehend deaktiviert ist, ohne den Text löschen zu müssen.
export function Step5Publish({ draft, onChange, project, projectId }: Step5Props) {
  const queryClient = useQueryClient();

  const publishMutation = useMutation({
    mutationFn: (publish: boolean) => (publish ? projectsApi.publish(projectId) : projectsApi.unpublish(projectId)),
    onSuccess: (updated) => {
      queryClient.setQueryData(["projects", projectId], updated);
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  const shareUrl = project.shareSlug ? `${window.location.origin}/c/${project.shareSlug}` : null;

  return (
    <>
      <label className={styles.toggleRow}>
        <input
          type="checkbox"
          checked={draft.saveConversations}
          onChange={(e) => onChange({ saveConversations: e.target.checked })}
        />
        <span className={styles.toggleCopy}>
          <strong>Konversationen aufzeichnen</strong>
          <span>Speichert Chatverläufe zur späteren Auswertung (Tab Auswertung). Standardmäßig aus.</span>
        </span>
      </label>

      <Callout variant="info">
        Die Umfrage wird per Iframe von Tally.so eingebettet — es wird kein zusätzliches Skript von
        tally.so geladen, nur die von dir eingefügte Formular-Adresse selbst. Für Schüler:innen ist die
        Teilnahme freiwillig und jederzeit überspringbar.
      </Callout>

      <div className={styles.field}>
        <label className={styles.toggleRow}>
          <input
            type="checkbox"
            checked={draft.surveyBeforeEnabled}
            onChange={(e) => onChange({ surveyBeforeEnabled: e.target.checked })}
          />
          <span className={styles.toggleCopy}>
            <strong>Umfrage vor dem Chat aktivieren</strong>
            <span>Wird angezeigt, bevor Schüler:innen den Chat starten können.</span>
          </span>
        </label>
        <Input
          label="Umfrage-URL (vor dem Chat)"
          type="url"
          placeholder="https://tally.so/r/xxxxxx"
          value={draft.surveyBeforeUrl}
          onChange={(e) => onChange({ surveyBeforeUrl: e.target.value })}
        />
        <p className={styles.hint}>
          Nur wirksam, wenn die Checkbox oben aktiviert ist. Leer lassen oder deaktivieren, um diesen
          Schritt zu überspringen. Für die korrekte Adresse ist die Lehrkraft selbst verantwortlich.
        </p>
      </div>

      <div className={styles.field}>
        <label className={styles.toggleRow}>
          <input
            type="checkbox"
            checked={draft.surveyAfterEnabled}
            onChange={(e) => onChange({ surveyAfterEnabled: e.target.checked })}
          />
          <span className={styles.toggleCopy}>
            <strong>Umfrage nach dem Chat aktivieren</strong>
            <span>Wird angezeigt, wenn Schüler:innen den Chat über "Chat beenden" abschließen.</span>
          </span>
        </label>
        <Input
          label="Umfrage-URL (nach dem Chat)"
          type="url"
          placeholder="https://tally.so/r/yyyyyy"
          value={draft.surveyAfterUrl}
          onChange={(e) => onChange({ surveyAfterUrl: e.target.value })}
        />
        <p className={styles.hint}>Nur wirksam, wenn die Checkbox oben aktiviert ist.</p>
      </div>

      <div className={styles.publishCard}>
        <div className={styles.publishHeader}>
          <Badge variant={project.published ? "accent" : "default"}>
            {project.published ? "Publiziert" : "Entwurf"}
          </Badge>
          <Button
            variant={project.published ? "default" : "accent"}
            onClick={() => publishMutation.mutate(!project.published)}
            // Ohne eingerichtetes Modell würde der öffentliche Chat nur ein "momentan nicht
            // verfügbar" zeigen — Depublizieren bleibt selbstverständlich immer möglich.
            disabled={publishMutation.isPending || (!project.published && !project.llmApiKeyId)}
          >
            {project.published ? "Depublizieren" : "Publizieren"}
          </Button>
        </div>

        {!project.published && !project.llmApiKeyId && (
          <Callout variant="warning">
            Zum Publizieren muss ein Modell gewählt und gespeichert sein.
          </Callout>
        )}

        {publishMutation.isError && (
          <Callout variant="danger">Aktion fehlgeschlagen. Bitte erneut versuchen.</Callout>
        )}

        {project.published && shareUrl && (
          <div className={styles.linkRow}>
            <span className={styles.linkField + " mono"}>{shareUrl}</span>
            <Button size="sm" onClick={() => navigator.clipboard.writeText(shareUrl)}>
              <Copy size={14} /> Kopieren
            </Button>
          </div>
        )}
      </div>
    </>
  );
}
