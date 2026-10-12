import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { ChevronRight } from "lucide-react";
import styles from "./AdvancedSection.module.css";

interface AdvancedSectionProps {
  /** Labels of the settings inside that differ from their defaults — named in the closed header, so
   * a changed value isn't silently hidden away. */
  changed?: string[];
  children: ReactNode;
}

/** Collapsible "Advanced settings" for options most teachers never need to touch. Native
 * <details>, so it's keyboard- and screen-reader-accessible as is; it always starts closed. */
export function AdvancedSection({ changed = [], children }: AdvancedSectionProps) {
  const { t } = useTranslation();
  return (
    <details className={styles.section}>
      <summary className={styles.summary}>
        <ChevronRight size={16} className={styles.chevron} aria-hidden="true" />
        <span className={styles.title}>{t("common.advancedSettings")}</span>
        {changed.length > 0 && (
          <span className={styles.changed}>{t("common.advancedChanged", { fields: changed.join(", ") })}</span>
        )}
      </summary>
      <div className={styles.content}>{children}</div>
    </details>
  );
}
