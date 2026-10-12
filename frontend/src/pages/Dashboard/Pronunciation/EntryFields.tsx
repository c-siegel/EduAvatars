// The inputs of one word-list entry — shared by the "add" form and the inline edit of a row, so
// both offer exactly the same options.

import { useTranslation } from "react-i18next";
import { Input } from "@/components/Input";
import type { PronunciationEntryInput } from "@/api/pronunciation";
import styles from "./Pronunciation.module.css";

export const EMPTY_INPUT: PronunciationEntryInput = {
  term: "",
  spoken: "",
  wholeWord: true,
  caseSensitive: false,
  spellOut: false,
};

const NUMBER_PLACEHOLDER = "{number}";

/** Mirrors the backend's spell_out() for the live preview ("GPT-4" -> "G P T 4"). */
export function spellOut(term: string): string {
  return Array.from(term)
    .filter((char) => /[\p{L}\p{N}]/u.test(char))
    .join(" ");
}

interface EntryFieldsProps {
  value: PronunciationEntryInput;
  onChange: (value: PronunciationEntryInput) => void;
  idPrefix: string;
}

export function EntryFields({ value, onChange, idPrefix }: EntryFieldsProps) {
  const { t } = useTranslation();
  const hasNumber = value.term.includes(NUMBER_PLACEHOLDER);

  function insertNumber() {
    const separator = value.term && !value.term.endsWith(" ") ? " " : "";
    onChange({ ...value, term: `${value.term}${separator}${NUMBER_PLACEHOLDER}`, spellOut: false });
  }

  return (
    <div className={styles.fields}>
      <div className={styles.fieldRow}>
        <div className={styles.field}>
          <Input
            id={`${idPrefix}-term`}
            label={t("pronunciation.term")}
            placeholder={t("pronunciation.termPlaceholder")}
            value={value.term}
            maxLength={100}
            onChange={(e) => onChange({ ...value, term: e.target.value })}
          />
          <button type="button" className={styles.linkButton} onClick={insertNumber}>
            {t("pronunciation.insertNumber")}
          </button>
        </div>
        <div className={styles.field}>
          <Input
            id={`${idPrefix}-spoken`}
            label={t("pronunciation.spoken")}
            placeholder={t("pronunciation.spokenPlaceholder")}
            value={value.spellOut ? spellOut(value.term) : value.spoken}
            maxLength={200}
            disabled={value.spellOut}
            onChange={(e) => onChange({ ...value, spoken: e.target.value })}
          />
        </div>
      </div>
      <div className={styles.options}>
        <label className={styles.option}>
          <input
            type="checkbox"
            checked={value.spellOut}
            disabled={hasNumber}
            onChange={(e) => onChange({ ...value, spellOut: e.target.checked })}
          />
          <span>{t("pronunciation.spellOut")}</span>
        </label>
        <label className={styles.option}>
          <input
            type="checkbox"
            checked={value.wholeWord}
            onChange={(e) => onChange({ ...value, wholeWord: e.target.checked })}
          />
          <span>{t("pronunciation.wholeWord")}</span>
        </label>
        <label className={styles.option}>
          <input
            type="checkbox"
            checked={value.caseSensitive}
            onChange={(e) => onChange({ ...value, caseSensitive: e.target.checked })}
          />
          <span>{t("pronunciation.caseSensitive")}</span>
        </label>
      </div>
    </div>
  );
}
