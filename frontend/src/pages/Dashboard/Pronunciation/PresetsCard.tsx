// Ready-made word lists (e.g. physics): look inside, copy into your own list, remove again.

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/Button";
import { Callout } from "@/components/Callout";
import { errorMessage } from "@/api/client";
import { pronunciationApi, type PresetPack } from "@/api/pronunciation";
import type { SpokenLanguage } from "@/types/project";
import { PRONUNCIATION_QUERY_KEY } from "./queries";
import styles from "./Pronunciation.module.css";

export function PresetsCard({ language }: { language: SpokenLanguage }) {
  const { t } = useTranslation();
  const presetsQuery = useQuery({
    queryKey: [...PRONUNCIATION_QUERY_KEY, "presets", language],
    queryFn: () => pronunciationApi.presets(language),
  });

  return (
    <div className={styles.card}>
      <h3>{t("pronunciation.presets.title")}</h3>
      <p className={styles.hint}>{t("pronunciation.presets.text")}</p>
      {presetsQuery.isLoading && <p className={styles.hint}>{t("common.loading")}</p>}
      {presetsQuery.isSuccess && presetsQuery.data.length === 0 && (
        <p className={styles.hint}>{t("pronunciation.presets.none")}</p>
      )}
      <ul className={styles.presetList}>
        {(presetsQuery.data ?? []).map((pack) => (
          <PresetRow key={`${pack.id}-${pack.language}`} pack={pack} />
        ))}
      </ul>
    </div>
  );
}

function PresetRow({ pack }: { pack: PresetPack }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [message, setMessage] = useState<string | null>(null);

  const applyMutation = useMutation({
    mutationFn: () => pronunciationApi.applyPreset(pack.id, pack.language),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: PRONUNCIATION_QUERY_KEY });
      setMessage(t("pronunciation.presets.applied", { added: result.added, skipped: result.skipped }));
    },
  });
  const removeMutation = useMutation({
    mutationFn: () => pronunciationApi.removePreset(pack.id, pack.language),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: PRONUNCIATION_QUERY_KEY });
      setMessage(t("pronunciation.presets.removed", { count: result.removed }));
    },
  });
  const name = t(`pronunciation.presets.packs.${pack.id}.name`, pack.id);
  const error = applyMutation.error ?? removeMutation.error;
  const busy = applyMutation.isPending || removeMutation.isPending;

  function handleRemove() {
    if (window.confirm(t("pronunciation.presets.removeConfirm", { name, count: pack.appliedCount }))) {
      removeMutation.mutate();
    }
  }

  return (
    <li className={styles.preset}>
      <div className={styles.presetTop}>
        <div>
          <strong>{name}</strong>
          <p className={styles.hint}>{t(`pronunciation.presets.packs.${pack.id}.description`, "")}</p>
          <p className={styles.hint}>
            {pack.appliedCount > 0
              ? t("pronunciation.presets.status", { count: pack.appliedCount, total: pack.entries.length })
              : t("pronunciation.presets.size", { total: pack.entries.length })}
          </p>
        </div>
        <div className={styles.actions}>
          <Button size="sm" variant="accent" onClick={() => applyMutation.mutate()} disabled={busy}>
            {pack.appliedCount > 0 ? t("pronunciation.presets.applyAgain") : t("pronunciation.presets.apply")}
          </Button>
          {pack.appliedCount > 0 && (
            <Button size="sm" onClick={handleRemove} disabled={busy}>
              {t("pronunciation.presets.remove")}
            </Button>
          )}
        </div>
      </div>
      {message && !error && <p className={styles.hint}>{message}</p>}
      {error && <Callout variant="danger">{errorMessage(error, t("pronunciation.presets.failed"))}</Callout>}
      <details>
        <summary className={styles.summary}>{t("pronunciation.presets.showEntries")}</summary>
        <ul className={styles.presetEntries}>
          {pack.entries.map((entry) => (
            <li key={entry.term}>
              <code className={styles.term}>{entry.term}</code> → {entry.spoken}
            </li>
          ))}
        </ul>
      </details>
    </li>
  );
}
