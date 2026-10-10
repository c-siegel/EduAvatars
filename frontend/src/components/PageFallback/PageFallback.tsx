import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import styles from "./PageFallback.module.css";

// Shown while a lazily loaded page's chunk downloads. Stays empty for the first moment, so a fast
// load doesn't flash a loading text that disappears again right away.
export function PageFallback() {
  const { t } = useTranslation();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const timeout = setTimeout(() => setVisible(true), 300);
    return () => clearTimeout(timeout);
  }, []);

  return (
    <div className={styles.fallback} role="status">
      {visible && t("common.loading")}
    </div>
  );
}
