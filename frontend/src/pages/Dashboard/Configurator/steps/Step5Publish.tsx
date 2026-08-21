import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
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
  const { t } = useTranslation();
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
          <strong>{t("configurator.step5.recordConversationsTitle")}</strong>
          <span>{t("configurator.step5.recordConversationsText")}</span>
        </span>
      </label>

      <Callout variant="info">{t("configurator.step5.surveyNotice")}</Callout>

      <div className={styles.field}>
        <label className={styles.toggleRow}>
          <input
            type="checkbox"
            checked={draft.surveyBeforeEnabled}
            onChange={(e) => onChange({ surveyBeforeEnabled: e.target.checked })}
          />
          <span className={styles.toggleCopy}>
            <strong>{t("configurator.step5.surveyBeforeTitle")}</strong>
            <span>{t("configurator.step5.surveyBeforeText")}</span>
          </span>
        </label>
        <Input
          label={t("configurator.step5.surveyBeforeUrl")}
          type="url"
          placeholder="https://tally.so/r/xxxxxx"
          value={draft.surveyBeforeUrl}
          onChange={(e) => onChange({ surveyBeforeUrl: e.target.value })}
        />
        <p className={styles.hint}>{t("configurator.step5.surveyBeforeHint")}</p>
      </div>

      <div className={styles.field}>
        <label className={styles.toggleRow}>
          <input
            type="checkbox"
            checked={draft.surveyAfterEnabled}
            onChange={(e) => onChange({ surveyAfterEnabled: e.target.checked })}
          />
          <span className={styles.toggleCopy}>
            <strong>{t("configurator.step5.surveyAfterTitle")}</strong>
            <span>{t("configurator.step5.surveyAfterText")}</span>
          </span>
        </label>
        <Input
          label={t("configurator.step5.surveyAfterUrl")}
          type="url"
          placeholder="https://tally.so/r/yyyyyy"
          value={draft.surveyAfterUrl}
          onChange={(e) => onChange({ surveyAfterUrl: e.target.value })}
        />
        <p className={styles.hint}>{t("configurator.step5.surveyAfterHint")}</p>
      </div>

      <div className={styles.publishCard}>
        <div className={styles.publishHeader}>
          <Badge variant={project.published ? "accent" : "default"}>
            {project.published ? t("overview.card.published") : t("overview.card.draft")}
          </Badge>
          <Button
            variant={project.published ? "default" : "accent"}
            onClick={() => publishMutation.mutate(!project.published)}
            // Ohne eingerichtetes Modell würde der öffentliche Chat nur ein "momentan nicht
            // verfügbar" zeigen — Depublizieren bleibt selbstverständlich immer möglich.
            disabled={publishMutation.isPending || (!project.published && !project.llmApiKeyId)}
          >
            {project.published ? t("configurator.step5.unpublish") : t("configurator.step5.publish")}
          </Button>
        </div>

        {!project.published && !project.llmApiKeyId && (
          <Callout variant="warning">{t("configurator.step5.publishNeedsModel")}</Callout>
        )}

        {publishMutation.isError && <Callout variant="danger">{t("configurator.step5.actionFailed")}</Callout>}

        {project.published && shareUrl && (
          <div className={styles.linkRow}>
            <span className={styles.linkField + " mono"}>{shareUrl}</span>
            <Button size="sm" onClick={() => navigator.clipboard.writeText(shareUrl)}>
              <Copy size={14} /> {t("configurator.step5.copy")}
            </Button>
          </div>
        )}
      </div>
    </>
  );
}
