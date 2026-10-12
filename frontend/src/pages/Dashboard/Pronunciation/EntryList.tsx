// The word list of one language: searchable, each row editable in place or deletable.

import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Pencil, Trash2 } from "lucide-react";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Callout } from "@/components/Callout";
import { errorMessage } from "@/api/client";
import { pronunciationApi, type PronunciationEntry, type PronunciationEntryInput } from "@/api/pronunciation";
import type { SpokenLanguage } from "@/types/project";
import { EntryFields } from "./EntryFields";
import { PRONUNCIATION_QUERY_KEY, useEntries } from "./queries";
import styles from "./Pronunciation.module.css";

export function EntryList({ language }: { language: SpokenLanguage }) {
  const { t } = useTranslation();
  const entriesQuery = useEntries(language);
  const [search, setSearch] = useState("");
  const entries = entriesQuery.data ?? [];

  const visible = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase();
    if (!needle) return entries;
    return entries.filter(
      (e) => e.term.toLocaleLowerCase().includes(needle) || e.spoken.toLocaleLowerCase().includes(needle),
    );
  }, [entries, search]);

  return (
    <div className={styles.card}>
      <div className={styles.cardTitleRow}>
        <h3>{t("pronunciation.listTitle", { count: entries.length })}</h3>
        {entries.length > 0 && (
          <input
            type="search"
            className={styles.search}
            placeholder={t("pronunciation.search")}
            aria-label={t("pronunciation.search")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        )}
      </div>
      {entriesQuery.isLoading && <p className={styles.hint}>{t("common.loading")}</p>}
      {entriesQuery.isError && (
        <Callout variant="danger">{errorMessage(entriesQuery.error, t("pronunciation.loadFailed"))}</Callout>
      )}
      {entriesQuery.isSuccess && entries.length === 0 && <p className={styles.hint}>{t("pronunciation.empty")}</p>}
      {entries.length > 0 && visible.length === 0 && <p className={styles.hint}>{t("pronunciation.noMatches")}</p>}
      <ul className={styles.entryList}>
        {visible.map((entry) => (
          <EntryRow key={entry.id} entry={entry} />
        ))}
      </ul>
    </div>
  );
}

function EntryRow({ entry }: { entry: PronunciationEntry }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<PronunciationEntryInput | null>(null);

  const updateMutation = useMutation({
    mutationFn: (input: PronunciationEntryInput) => pronunciationApi.update(entry.id, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PRONUNCIATION_QUERY_KEY });
      setEditing(null);
    },
  });
  const removeMutation = useMutation({
    mutationFn: () => pronunciationApi.remove(entry.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: PRONUNCIATION_QUERY_KEY }),
  });

  function startEditing() {
    updateMutation.reset();
    setEditing({
      term: entry.term,
      spoken: entry.spoken,
      wholeWord: entry.wholeWord,
      caseSensitive: entry.caseSensitive,
      spellOut: false,
    });
  }

  if (editing) {
    return (
      <li className={styles.entryEditing}>
        <EntryFields value={editing} onChange={setEditing} idPrefix={`entry-${entry.id}`} />
        {updateMutation.isError && (
          <Callout variant="danger">{errorMessage(updateMutation.error, t("pronunciation.saveFailed"))}</Callout>
        )}
        <div className={styles.actions}>
          <Button
            size="sm"
            variant="accent"
            onClick={() => updateMutation.mutate(editing)}
            disabled={!editing.term.trim() || updateMutation.isPending}
          >
            {t("pronunciation.save")}
          </Button>
          <Button size="sm" onClick={() => setEditing(null)}>
            {t("pronunciation.cancel")}
          </Button>
        </div>
      </li>
    );
  }

  return (
    <li className={styles.entry}>
      <div className={styles.entryText}>
        <code className={styles.term}>{entry.term}</code>
        <span className={styles.arrow} aria-hidden="true">
          →
        </span>
        <span>{entry.spoken}</span>
      </div>
      <div className={styles.entryMeta}>
        {!entry.wholeWord && <Badge>{t("pronunciation.badgePartOfWord")}</Badge>}
        {entry.caseSensitive && <Badge>{t("pronunciation.badgeCaseSensitive")}</Badge>}
        {entry.sourcePack && (
          <Badge variant="accent">{t(`pronunciation.presets.packs.${entry.sourcePack}.name`, entry.sourcePack)}</Badge>
        )}
        <Button size="sm" onClick={startEditing} aria-label={t("pronunciation.edit")} title={t("pronunciation.edit")}>
          <Pencil size={14} />
        </Button>
        <Button
          size="sm"
          onClick={() => removeMutation.mutate()}
          disabled={removeMutation.isPending}
          aria-label={t("pronunciation.remove")}
          title={t("pronunciation.remove")}
        >
          <Trash2 size={14} />
        </Button>
      </div>
    </li>
  );
}
