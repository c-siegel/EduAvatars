// Moving whole word lists in and out: paste text or pick a .txt/.csv file, check what would
// change (dry run), then import; or download the list as CSV to edit in a spreadsheet or share
// with a colleague.

import { useState, type ChangeEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Download } from "lucide-react";
import { Button } from "@/components/Button";
import { Callout } from "@/components/Callout";
import { Textarea } from "@/components/Input";
import { errorMessage } from "@/api/client";
import { pronunciationApi, type ImportResult } from "@/api/pronunciation";
import type { SpokenLanguage } from "@/types/project";
import { PRONUNCIATION_QUERY_KEY } from "./queries";
import styles from "./Pronunciation.module.css";

// Matches the backend's PronunciationImportIn.text limit.
const MAX_IMPORT_CHARS = 200_000;

export function ImportExportCard({ language }: { language: SpokenLanguage }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [text, setText] = useState("");
  const [overwrite, setOverwrite] = useState(false);
  // The dry-run result the teacher is looking at; importing for real clears it.
  const [check, setCheck] = useState<ImportResult | null>(null);
  const [imported, setImported] = useState<ImportResult | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);

  const checkMutation = useMutation({
    mutationFn: () => pronunciationApi.import(language, text, overwrite, true),
    onSuccess: (result) => {
      setCheck(result);
      setImported(null);
    },
  });
  const importMutation = useMutation({
    mutationFn: () => pronunciationApi.import(language, text, overwrite, false),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: PRONUNCIATION_QUERY_KEY });
      setImported(result);
      setCheck(null);
      setText("");
    },
  });
  const exportMutation = useMutation({ mutationFn: () => pronunciationApi.exportCsv(language) });

  function resetResults() {
    setCheck(null);
    setImported(null);
    checkMutation.reset();
    importMutation.reset();
  }

  async function handleFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setFileError(null);
    if (file.size > MAX_IMPORT_CHARS * 4) {
      setFileError(t("pronunciation.importExport.fileTooLarge"));
      return;
    }
    const content = await file.text();
    if (content.length > MAX_IMPORT_CHARS) {
      setFileError(t("pronunciation.importExport.fileTooLarge"));
      return;
    }
    setText(content);
    resetResults();
  }

  const result = imported ?? check;
  const error = checkMutation.error ?? importMutation.error;

  return (
    <div className={styles.card}>
      <h3>{t("pronunciation.importExport.title")}</h3>
      <p className={styles.hint}>{t("pronunciation.importExport.text")}</p>
      <pre className={styles.formatExample}>{t("pronunciation.importExport.example")}</pre>

      <Textarea
        label={t("pronunciation.importExport.paste")}
        value={text}
        rows={5}
        maxLength={MAX_IMPORT_CHARS}
        onChange={(e) => {
          setText(e.target.value);
          resetResults();
        }}
      />
      <label className={styles.fileLabel}>
        <span>{t("pronunciation.importExport.file")}</span>
        <input type="file" accept=".txt,.csv,.tsv,text/plain,text/csv" onChange={handleFile} />
      </label>
      {fileError && <p className={styles.error}>{fileError}</p>}

      <label className={styles.option}>
        <input
          type="checkbox"
          checked={overwrite}
          onChange={(e) => {
            setOverwrite(e.target.checked);
            resetResults();
          }}
        />
        <span>{t("pronunciation.importExport.overwrite")}</span>
      </label>

      {error && <Callout variant="danger">{errorMessage(error, t("pronunciation.importExport.failed"))}</Callout>}
      {result && (
        <div className={styles.importResult}>
          <p>
            {t(imported ? "pronunciation.importExport.done" : "pronunciation.importExport.wouldDo", {
              added: result.added,
              updated: result.updated,
              skipped: result.skipped,
            })}
          </p>
          {result.errors.length > 0 && (
            <>
              <p className={styles.error}>{t("pronunciation.importExport.lineErrors", { count: result.errors.length })}</p>
              <ul className={styles.lineErrors}>
                {result.errors.map((lineError) => (
                  <li key={lineError.line}>
                    {t("pronunciation.importExport.line", { line: lineError.line })}{" "}
                    <code>{lineError.content}</code> — {t(`errors.${lineError.error}`, lineError.error)}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}

      <div className={styles.actions}>
        <Button onClick={() => checkMutation.mutate()} disabled={!text.trim() || checkMutation.isPending}>
          {t("pronunciation.importExport.check")}
        </Button>
        <Button
          variant="accent"
          onClick={() => importMutation.mutate()}
          disabled={!text.trim() || importMutation.isPending}
        >
          {t("pronunciation.importExport.import")}
        </Button>
        <Button onClick={() => exportMutation.mutate()} disabled={exportMutation.isPending}>
          <Download size={14} /> {t("pronunciation.importExport.export")}
        </Button>
      </div>
      {exportMutation.isError && (
        <Callout variant="danger">{errorMessage(exportMutation.error, t("pronunciation.importExport.exportFailed"))}</Callout>
      )}
    </div>
  );
}
