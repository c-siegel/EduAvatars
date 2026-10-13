import { useTranslation } from "react-i18next";
import styles from "./Wordmark.module.css";

/**
 * The LOLA logo: the O is a talking speech-bubble face, a yellow spark marks the voice, and the
 * tagline below is set exactly as wide as the name. Drawn as inline SVG so its colours follow the
 * --logo-* tokens in light and dark mode.
 */
export function Wordmark() {
  const { t } = useTranslation();
  return (
    <svg className={styles.wordmark} viewBox="0 0 212 104" role="img" aria-label={`LOLA – ${t("brand.tagline")}`}>
      <text x="4" y="68" className={styles.letters}>
        L
      </text>
      <circle cx="79" cy="44" r="25" className={styles.bubble} />
      <path d="M61 59 L53 77 L73 66 Z" className={styles.bubble} />
      <circle cx="71" cy="40" r="3.4" className={styles.face} />
      <circle cx="87" cy="40" r="3.4" className={styles.face} />
      <path d="M70 50 Q79 57.5 88 50" className={styles.smile} />
      <circle cx="104.5" cy="19.5" r="4.6" className={styles.spark} />
      <text x="112" y="68" className={styles.letters}>
        L
      </text>
      <text x="152" y="68" className={styles.letters}>
        A
      </text>
      {/* textLength stretches the tagline to the width of "LOLA" in either language. */}
      <text x="9" y="98" textLength="189" lengthAdjust="spacing" className={styles.tagline}>
        {t("brand.tagline").toUpperCase()}
      </text>
    </svg>
  );
}
