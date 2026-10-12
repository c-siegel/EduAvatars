// Configurator step 3, "Knowledge": which of the teacher's knowledge bases the avatar may draw on,
// and how strictly. Hidden entirely when the deployment has no knowledge service; disabled for
// GWDG Arcana keys, which bring their own knowledge base (see backend
// features/knowledge/retrieval.py::prepare_knowledge).

import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Callout } from "@/components/Callout";
import { InfoButton, InfoPanel, LabelWithInfo, useInfoTip } from "@/components/InfoTip";
import { apiKeysApi } from "@/api/apiKeys";
import { knowledgeApi } from "@/api/knowledge";
import { useKnowledgeStatus } from "@/lib/providers";
import { KNOWLEDGE_MODES } from "@/types/project";
import type { StepProps } from "../types";
import styles from "./KnowledgeSection.module.css";

const ARCANA_PROVIDER = "gwdg_arcana";
const MAX_TOP_K = 8;

export function KnowledgeSection({ draft, onChange }: StepProps) {
  const { t } = useTranslation();
  const introTip = useInfoTip();
  const modeTip = useInfoTip();
  const status = useKnowledgeStatus().data;
  const available = status?.available ?? false;
  const kbQuery = useQuery({ queryKey: ["knowledge-bases"], queryFn: knowledgeApi.list, enabled: available });
  const keysQuery = useQuery({ queryKey: ["api-keys"], queryFn: apiKeysApi.list, enabled: available });

  if (!available) return null;

  const knowledgeBases = kbQuery.data ?? [];
  const llmKey = (keysQuery.data ?? []).find((key) => key.id === draft.llmApiKeyId);
  const usesArcana = llmKey?.provider === ARCANA_PROVIDER;
  const active = draft.knowledgeMode !== "off";

  function toggleBase(id: string, checked: boolean) {
    const ids = checked ? [...draft.knowledgeBaseIds, id] : draft.knowledgeBaseIds.filter((other) => other !== id);
    onChange({ knowledgeBaseIds: ids });
  }

  return (
    <section className={styles.section} aria-labelledby="knowledge-section-title">
      <div className={styles.titleRow}>
        <h3 id="knowledge-section-title" className={styles.title}>
          {t("configurator.knowledge.title")}
        </h3>
        <InfoButton
          topic={t("configurator.knowledge.title")}
          open={introTip.open}
          panelId={introTip.panelId}
          onToggle={introTip.toggle}
        />
      </div>
      <InfoPanel id={introTip.panelId} open={introTip.open}>
        {t("configurator.knowledge.intro")}
      </InfoPanel>

      {usesArcana ? (
        <Callout variant="info">{t("configurator.knowledge.arcanaHint")}</Callout>
      ) : (
        <>
          <div className={styles.titleRow}>
            <span className={styles.label} id="knowledge-mode-label">
              {t("configurator.knowledge.modeLabel")}
            </span>
            <InfoButton
              topic={t("configurator.knowledge.modeLabel")}
              open={modeTip.open}
              panelId={modeTip.panelId}
              onToggle={modeTip.toggle}
            />
          </div>
          <InfoPanel id={modeTip.panelId} open={modeTip.open}>
            <ul className={styles.modeHints}>
              {KNOWLEDGE_MODES.map((mode) => (
                <li key={mode}>
                  <strong>{t(`configurator.knowledge.modes.${mode}`)}:</strong>{" "}
                  {t(`configurator.knowledge.modeHints.${mode}`)}
                </li>
              ))}
            </ul>
          </InfoPanel>
          <div className={styles.modes} role="radiogroup" aria-labelledby="knowledge-mode-label">
            {KNOWLEDGE_MODES.map((mode) => (
              <label key={mode} className={styles.mode}>
                <input
                  type="radio"
                  name="knowledge-mode"
                  checked={draft.knowledgeMode === mode}
                  onChange={() => onChange({ knowledgeMode: mode })}
                />
                <strong>{t(`configurator.knowledge.modes.${mode}`)}</strong>
              </label>
            ))}
          </div>

          {active && (
            <>
              {knowledgeBases.length === 0 ? (
                <Callout variant="warning">
                  {t("configurator.knowledge.noBases")}{" "}
                  <Link to="/dashboard/knowledge">{t("configurator.knowledge.manageLink")}</Link>
                </Callout>
              ) : (
                <fieldset className={styles.bases}>
                  <legend className={styles.label}>{t("configurator.knowledge.basesLabel")}</legend>
                  {knowledgeBases.map((kb) => (
                    <label key={kb.id} className={styles.base}>
                      <input
                        type="checkbox"
                        checked={draft.knowledgeBaseIds.includes(kb.id)}
                        onChange={(e) => toggleBase(kb.id, e.target.checked)}
                      />
                      <span>
                        {kb.name}{" "}
                        <span className={styles.hint}>
                          {t("configurator.knowledge.baseMeta", { count: kb.documentCount })}
                          {!kb.embeddingAvailable && ` · ${t("knowledge.embeddingUnavailable")}`}
                        </span>
                      </span>
                    </label>
                  ))}
                </fieldset>
              )}
              {draft.knowledgeBaseIds.length === 0 && knowledgeBases.length > 0 && (
                <p className={styles.hint}>{t("configurator.knowledge.noneSelected")}</p>
              )}

              <div className={styles.topK}>
                <LabelWithInfo
                  label={t("configurator.knowledge.topK")}
                  htmlFor="knowledge-top-k"
                  className={styles.label}
                  info={t("configurator.knowledge.topKHint")}
                />
                <input
                  id="knowledge-top-k"
                  type="number"
                  min={1}
                  max={MAX_TOP_K}
                  value={draft.knowledgeTopK}
                  onChange={(e) =>
                    onChange({ knowledgeTopK: Math.min(MAX_TOP_K, Math.max(1, Math.floor(Number(e.target.value) || 1))) })
                  }
                />
              </div>

              <Callout variant="warning">{t("configurator.knowledge.publicNotice")}</Callout>
            </>
          )}
        </>
      )}
    </section>
  );
}
