import { useTranslation } from "react-i18next";
import styles from "./LanguageSwitcher.module.css";

const LANGUAGES = [
  { code: "de", label: "DE" },
  { code: "en", label: "EN" },
] as const;

/** Toggle between German and English; the choice is persisted to localStorage by i18next.
 * `compact` renders a single button naming the other language instead of the two-option pill —
 * for tight spots like the chat header on a phone, where the pill crowded out the tutor's name. */
export function LanguageSwitcher({ compact = false }: { compact?: boolean }) {
  const { t, i18n } = useTranslation();
  const current = i18n.language.startsWith("en") ? "en" : "de";

  if (compact) {
    const other = LANGUAGES.find(({ code }) => code !== current)!;
    // Labelled in the language it switches to, since that's the one the visitor can read.
    return (
      <button
        type="button"
        className={styles.compact}
        lang={other.code}
        aria-label={t("languageSwitcher.switchTo", { lng: other.code })}
        title={t("languageSwitcher.switchTo", { lng: other.code })}
        onClick={() => i18n.changeLanguage(other.code)}
      >
        <span className={styles.compactLabel}>{other.label}</span>
      </button>
    );
  }

  return (
    <div className={styles.switcher} role="group" aria-label="Sprache / Language">
      {LANGUAGES.map(({ code, label }) => (
        <button
          key={code}
          type="button"
          className={`${styles.option} ${current === code ? styles.optionActive : ""}`}
          aria-pressed={current === code}
          onClick={() => i18n.changeLanguage(code)}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
