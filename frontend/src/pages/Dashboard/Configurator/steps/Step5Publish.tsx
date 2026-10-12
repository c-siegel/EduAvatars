import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Copy } from "lucide-react";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Callout } from "@/components/Callout";
import { HeadingWithInfo, ToggleWithInfo } from "@/components/InfoTip";
import { Input } from "@/components/Input";
import { errorMessage } from "@/api/client";
import { projectsApi } from "@/api/projects";
import type { Project } from "@/types/project";
import type { StepProps } from "../types";
import styles from "./shared.module.css";

interface Step5Props extends StepProps {
  project: Project;
  projectId: string;
  /** Whether the draft (this step's fields included) differs from the last-saved project. */
  hasUnsavedChanges: boolean;
  /** Persists the current draft; publish/unpublish call this first so they never act on stale data. */
  onSaveDraft: () => Promise<Project>;
}

// Step 5 — publishing: recording, surveys and the actual publishing.
// The surveys' checkbox and URL are deliberately separate fields: a URL can stay in place while
// the survey is temporarily disabled, without having to delete the text.
export function Step5Publish({ draft, onChange, project, projectId, hasUnsavedChanges, onSaveDraft }: Step5Props) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const publishMutation = useMutation({
    // Publishing/unpublishing only flips the published flag server-side — it never persists
    // draft edits from steps 1-3 (or this step's own fields). Save first, or a teacher who
    // edits and immediately publishes would ship the previous saved version instead.
    mutationFn: async (publish: boolean) => {
      if (hasUnsavedChanges) {
        await onSaveDraft();
      }
      return publish ? projectsApi.publish(projectId) : projectsApi.unpublish(projectId);
    },
    onSuccess: (updated) => {
      queryClient.setQueryData(["projects", projectId], updated);
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  const shareUrl = project.shareSlug ? `${window.location.origin}/c/${project.shareSlug}` : null;

  // Deliberately not part of `draft`/onChange (like published/shareSlug above) — this is
  // server-owned status set through its own mutation, not part of the wizard's draft/dirty flow.
  const [chatPasswordInput, setChatPasswordInput] = useState("");
  const [editingChatPassword, setEditingChatPassword] = useState(false);

  const chatPasswordMutation = useMutation({
    mutationFn: (chatPassword: string | null) => projectsApi.update(projectId, { chatPassword }),
    onSuccess: (updated) => {
      queryClient.setQueryData(["projects", projectId], updated);
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setChatPasswordInput("");
      setEditingChatPassword(false);
    },
  });

  function handleSetChatPassword(event: FormEvent) {
    event.preventDefault();
    if (!chatPasswordInput.trim() || chatPasswordMutation.isPending) return;
    chatPasswordMutation.mutate(chatPasswordInput);
  }

  return (
    <>
      <ToggleWithInfo
        title={t("configurator.step5.recordConversationsTitle")}
        checked={draft.saveConversations}
        onChange={(e) => onChange({ saveConversations: e.target.checked })}
        info={t("configurator.step5.recordConversationsText")}
      />

      <ToggleWithInfo
        title={t("configurator.step5.requireVisitorNameTitle")}
        checked={draft.requireVisitorName}
        onChange={(e) => onChange({ requireVisitorName: e.target.checked })}
        info={t("configurator.step5.requireVisitorNameText")}
      />

      <Callout variant="info">{t("configurator.step5.surveyNotice")}</Callout>

      <div className={styles.field}>
        <ToggleWithInfo
          title={t("configurator.step5.surveyBeforeTitle")}
          checked={draft.surveyBeforeEnabled}
          onChange={(e) => onChange({ surveyBeforeEnabled: e.target.checked })}
          info={t("configurator.step5.surveyBeforeText")}
        />
        <Input
          label={t("configurator.step5.surveyBeforeUrl")}
          type="url"
          placeholder="https://tally.so/r/xxxxxx"
          value={draft.surveyBeforeUrl}
          onChange={(e) => onChange({ surveyBeforeUrl: e.target.value })}
          info={t("configurator.step5.surveyBeforeHint")}
        />
      </div>

      <div className={styles.field}>
        <ToggleWithInfo
          title={t("configurator.step5.surveyAfterTitle")}
          checked={draft.surveyAfterEnabled}
          onChange={(e) => onChange({ surveyAfterEnabled: e.target.checked })}
          info={t("configurator.step5.surveyAfterText")}
        />
        <Input
          label={t("configurator.step5.surveyAfterUrl")}
          type="url"
          placeholder="https://tally.so/r/yyyyyy"
          value={draft.surveyAfterUrl}
          onChange={(e) => onChange({ surveyAfterUrl: e.target.value })}
          info={t("configurator.step5.surveyAfterHint")}
        />
      </div>

      <div className={styles.publishCard}>
        <div className={styles.publishHeader}>
          <Badge variant={project.published ? "accent" : "default"}>
            {project.published ? t("overview.card.published") : t("overview.card.draft")}
          </Badge>
          <Button
            variant={project.published ? "default" : "accent"}
            onClick={() => publishMutation.mutate(!project.published)}
            // Without a configured model the public chat would only show "currently
            // unavailable" — unpublishing of course always stays possible.
            disabled={publishMutation.isPending || (!project.published && !draft.llmApiKeyId)}
          >
            {project.published ? t("configurator.step5.unpublish") : t("configurator.step5.publish")}
          </Button>
        </div>

        {!project.published && !draft.llmApiKeyId && (
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

      <div className={styles.publishCard}>
        <div className={styles.publishHeader}>
          <HeadingWithInfo
            as="h4"
            className={styles.cardTitle}
            title={t("configurator.step5.passwordProtection.title")}
            info={t("configurator.step5.passwordProtection.text")}
          />
          <Badge variant={project.passwordProtected ? "accent" : "default"}>
            {project.passwordProtected
              ? t("configurator.step5.passwordProtection.protected")
              : t("configurator.step5.passwordProtection.notProtected")}
          </Badge>
        </div>

        {chatPasswordMutation.isError && (
          <Callout variant="danger">
            {errorMessage(chatPasswordMutation.error, t("configurator.step5.actionFailed"))}
          </Callout>
        )}

        {project.passwordProtected && !editingChatPassword && (
          <div className={styles.linkRow}>
            <Button size="sm" onClick={() => setEditingChatPassword(true)}>
              {t("configurator.step5.passwordProtection.change")}
            </Button>
            <Button
              size="sm"
              variant="danger"
              onClick={() => chatPasswordMutation.mutate(null)}
              disabled={chatPasswordMutation.isPending}
            >
              {t("configurator.step5.passwordProtection.remove")}
            </Button>
          </div>
        )}

        {(!project.passwordProtected || editingChatPassword) && (
          <form className={styles.linkRow} onSubmit={handleSetChatPassword}>
            <Input
              label={t("configurator.step5.passwordProtection.passwordLabel")}
              type="text"
              value={chatPasswordInput}
              onChange={(e) => setChatPasswordInput(e.target.value)}
            />
            <Button type="submit" size="sm" disabled={chatPasswordMutation.isPending}>
              {t("configurator.step5.passwordProtection.save")}
            </Button>
            {editingChatPassword && (
              <Button type="button" size="sm" onClick={() => setEditingChatPassword(false)}>
                {t("common.cancel")}
              </Button>
            )}
          </form>
        )}
      </div>
    </>
  );
}
