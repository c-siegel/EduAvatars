import { useTranslation } from "react-i18next";
import styles from "./LanguageSwitcher.module.css";

const LANGUAGES = [
  { code: "de", label: "DE" },
  { code: "en", label: "EN" },
] as const;

/** Toggle between German and English; the choice is persisted to localStorage by i18next. */
export function LanguageSwitcher() {
  const { i18n } = useTranslation();
  const current = i18n.language.startsWith("en") ? "en" : "de";

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
