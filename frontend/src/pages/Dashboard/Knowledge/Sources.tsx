// Source details of knowledge documents: what a document is (title, author, year, kind of source,
// how much to rely on it), so the avatar can judge it and cite it when asked where something comes
// from. Three layers, combined by the backend (backend/app/features/knowledge/metadata.py): what the
// teacher enters here wins over the linked bibliography entry (an imported .bib file), which wins
// over the header at the top of a Markdown/text file. Never re-indexes anything.

import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Trash2, Upload } from "lucide-react";
import { Button } from "@/components/Button";
import { Callout } from "@/components/Callout";
import { errorMessage } from "@/api/client";
import {
  SOURCE_PRIORITIES,
  SOURCE_TYPES,
  knowledgeApi,
  type BibImportResult,
  type KnowledgeBase,
  type KnowledgeDocument,
  type SourceMetadata,
} from "@/api/knowledge";
import styles from "./Knowledge.module.css";

/** The citation (or title/author/year) under a document's file name. */
export function SourceSummary({ document }: { document: KnowledgeDocument }) {
  const { t } = useTranslation();
  const meta = document.metadata;
  if (!meta.cite && !meta.sourceType && !meta.priority) return null;
  const tags = [
    meta.sourceType ? t(`sources.type.${meta.sourceType}`) : null,
    meta.priority ? t(`sources.priority.${meta.priority}`) : null,
    meta.bibtexKey ? `@${meta.bibtexKey}` : null,
  ].filter(Boolean);
  return (
    <span className={styles.sourceSummary}>
      {meta.cite && <span className={styles.cite}>{meta.cite}</span>}
      {tags.length > 0 && <span className={styles.hint}>{tags.join(" · ")}</span>}
    </span>
  );
}

type TextField = "title" | "author" | "container" | "url" | "citation" | "note" | "bibtexKey";
const TEXT_FIELDS: { field: TextField; maxLength: number; wide?: boolean }[] = [
  { field: "title", maxLength: 300, wide: true },
  { field: "author", maxLength: 300, wide: true },
  { field: "container", maxLength: 200 },
  { field: "url", maxLength: 500 },
  { field: "citation", maxLength: 500, wide: true },
  { field: "note", maxLength: 300, wide: true },
];

type Draft = Record<TextField | "year" | "sourceType" | "priority", string>;

function toDraft(own: SourceMetadata): Draft {
  return {
    title: own.title ?? "",
    author: own.author ?? "",
    year: own.year ? String(own.year) : "",
    container: own.container ?? "",
    url: own.url ?? "",
    citation: own.citation ?? "",
    sourceType: own.sourceType ?? "",
    priority: own.priority ?? "",
    note: own.note ?? "",
    bibtexKey: own.bibtexKey ?? "",
  };
}

function fromDraft(draft: Draft): Partial<SourceMetadata> {
  const out: Record<string, string | number> = {};
  for (const [key, value] of Object.entries(draft)) {
    const trimmed = value.trim();
    if (trimmed) out[key] = key === "year" ? Number(trimmed) : trimmed;
  }
  return out as Partial<SourceMetadata>;
}

/** The form for one document's own source details; empty fields show what's inherited. */
export function SourceForm({
  document,
  kb,
  onClose,
}: {
  document: KnowledgeDocument;
  kb: KnowledgeBase;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const entries = useQuery({ queryKey: ["bibliography", kb.id], queryFn: () => knowledgeApi.bibliography(kb.id) }).data ?? [];
  const [draft, setDraft] = useState<Draft>(() => toDraft(document.ownMetadata));
  const inherited = document.metadata;
  const idPrefix = `source-${document.id}`;

  const saveMutation = useMutation({
    mutationFn: (body: Partial<SourceMetadata>) => knowledgeApi.updateMetadata(document.id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge-documents", kb.id] });
      onClose();
    },
  });

  function set(field: keyof Draft, value: string) {
    setDraft((current) => ({ ...current, [field]: value }));
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    saveMutation.mutate(fromDraft(draft));
  }

  // What a cleared field falls back to — shown as a placeholder.
  function placeholder(field: keyof SourceMetadata): string {
    const value = inherited[field];
    return value === null || value === undefined || draft[field as keyof Draft] ? "" : String(value);
  }

  return (
    <form className={styles.sourceForm} onSubmit={handleSubmit}>
      <p className={styles.hint}>{t("sources.formHint")}</p>
      <div className={styles.sourceGrid}>
        {TEXT_FIELDS.map(({ field, maxLength, wide }) => (
          <div key={field} className={`${styles.field} ${wide ? styles.wide : ""}`}>
            <label className={styles.label} htmlFor={`${idPrefix}-${field}`}>
              {t(`sources.field.${field}`)}
            </label>
            <input
              id={`${idPrefix}-${field}`}
              className={styles.sourceInput}
              type={field === "url" ? "url" : "text"}
              maxLength={maxLength}
              value={draft[field]}
              placeholder={placeholder(field)}
              onChange={(e) => set(field, e.target.value)}
            />
          </div>
        ))}
        <div className={styles.field}>
          <label className={styles.label} htmlFor={`${idPrefix}-year`}>
            {t("sources.field.year")}
          </label>
          <input
            id={`${idPrefix}-year`}
            className={styles.sourceInput}
            type="number"
            min={1000}
            max={2100}
            value={draft.year}
            placeholder={placeholder("year")}
            onChange={(e) => set("year", e.target.value)}
          />
        </div>
        <div className={styles.field}>
          <label className={styles.label} htmlFor={`${idPrefix}-type`}>
            {t("sources.field.sourceType")}
          </label>
          <select
            id={`${idPrefix}-type`}
            className={styles.select}
            value={draft.sourceType}
            onChange={(e) => set("sourceType", e.target.value)}
          >
            <option value="">
              {inherited.sourceType && !draft.sourceType
                ? t("sources.inherited", { value: t(`sources.type.${inherited.sourceType}`) })
                : t("sources.none")}
            </option>
            {SOURCE_TYPES.map((type) => (
              <option key={type} value={type}>
                {t(`sources.type.${type}`)}
              </option>
            ))}
          </select>
        </div>
        <div className={styles.field}>
          <label className={styles.label} htmlFor={`${idPrefix}-priority`}>
            {t("sources.field.priority")}
          </label>
          <select
            id={`${idPrefix}-priority`}
            className={styles.select}
            value={draft.priority}
            onChange={(e) => set("priority", e.target.value)}
          >
            <option value="">
              {inherited.priority && !draft.priority
                ? t("sources.inherited", { value: t(`sources.priority.${inherited.priority}`) })
                : t("sources.none")}
            </option>
            {SOURCE_PRIORITIES.map((priority) => (
              <option key={priority} value={priority}>
                {t(`sources.priority.${priority}`)}
              </option>
            ))}
          </select>
        </div>
        <div className={styles.field}>
          <label className={styles.label} htmlFor={`${idPrefix}-bibtexKey`}>
            {t("sources.field.bibtexKey")}
          </label>
          <input
            id={`${idPrefix}-bibtexKey`}
            className={styles.sourceInput}
            list={`${idPrefix}-entries`}
            maxLength={100}
            value={draft.bibtexKey}
            placeholder={placeholder("bibtexKey")}
            onChange={(e) => set("bibtexKey", e.target.value)}
          />
          <datalist id={`${idPrefix}-entries`}>
            {entries.map((entry) => (
              <option key={entry.key} value={entry.key}>
                {[entry.author, entry.year, entry.title].filter(Boolean).join(" · ")}
              </option>
            ))}
          </datalist>
        </div>
      </div>
      <p className={styles.hint}>{t("sources.studentsSee")}</p>
      {saveMutation.isError && <Callout variant="danger">{errorMessage(saveMutation.error, t("sources.saveFailed"))}</Callout>}
      <div className={styles.retryRow}>
        <Button type="submit" size="sm" variant="accent" disabled={saveMutation.isPending}>
          {t("sources.save")}
        </Button>
        <Button
          size="sm"
          onClick={() => saveMutation.mutate({})}
          disabled={saveMutation.isPending || Object.values(draft).every((v) => !v)}
        >
          {t("sources.clearOwn")}
        </Button>
        <Button size="sm" onClick={onClose}>
          {t("sources.cancel")}
        </Button>
      </div>
    </form>
  );
}

/** A knowledge base's bibliography: import a .bib file, documents are linked by BibTeX key. */
export function Bibliography({ kb }: { kb: KnowledgeBase }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const entriesQuery = useQuery({ queryKey: ["bibliography", kb.id], queryFn: () => knowledgeApi.bibliography(kb.id) });
  const entries = entriesQuery.data ?? [];
  const [result, setResult] = useState<BibImportResult | null>(null);
  const [inputKey, setInputKey] = useState(0);

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ["bibliography", kb.id] });
    queryClient.invalidateQueries({ queryKey: ["knowledge-documents", kb.id] });
  }

  const importMutation = useMutation({
    mutationFn: (file: File) => knowledgeApi.importBibliography(kb.id, file),
    onSuccess: (data) => {
      setResult(data);
      setInputKey((key) => key + 1);
      refresh();
    },
  });
  const removeMutation = useMutation({
    mutationFn: () => knowledgeApi.removeBibliography(kb.id),
    onSuccess: () => {
      setResult(null);
      refresh();
    },
  });

  return (
    <section className={styles.upload}>
      <h4>{t("sources.bibTitle")}</h4>
      <p className={styles.hint}>{t("sources.bibHint")}</p>
      <div className={styles.retryRow}>
        <label className={styles.fileButton}>
          <Upload size={14} /> {t("sources.bibImport")}
          <input
            key={inputKey}
            type="file"
            accept=".bib,text/x-bibtex,application/x-bibtex"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) importMutation.mutate(file);
            }}
          />
        </label>
        {entries.length > 0 && (
          <>
            <span className={styles.hint}>{t("sources.bibCount", { count: entries.length })}</span>
            <Button
              size="sm"
              onClick={() => {
                if (window.confirm(t("sources.bibRemoveConfirm"))) removeMutation.mutate();
              }}
              disabled={removeMutation.isPending}
              aria-label={t("sources.bibRemove")}
              title={t("sources.bibRemove")}
            >
              <Trash2 size={14} />
            </Button>
          </>
        )}
      </div>
      {importMutation.isPending && <p className={styles.hint}>{t("common.loading")}</p>}
      {result && (
        <Callout variant={result.unlinked.length ? "info" : "success"}>
          {t("sources.bibResult", { entries: result.entries, linked: result.linked })}
          {result.skipped > 0 && ` ${t("sources.bibSkipped", { count: result.skipped })}`}
          {result.unlinked.length > 0 && (
            <>
              {" "}
              {t("sources.bibUnlinked", { names: result.unlinked.join(", ") })}
            </>
          )}
        </Callout>
      )}
      {importMutation.isError && (
        <Callout variant="danger">{errorMessage(importMutation.error, t("sources.bibFailed"))}</Callout>
      )}
    </section>
  );
}
