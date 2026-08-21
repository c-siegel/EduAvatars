import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import styles from "./Toast.module.css";

interface ToastProps {
  message: string;
  onDismiss: () => void;
}

// Speichern-Bestätigung (Screen 1h), auch in 1e für "Fortschritt gespeichert." genutzt.
// Desktop oben rechts, Mobile unten über der Safe Area (siehe Wireframe-Annotation zu 1h),
// Auto-Dismiss nach ~4s.
export function Toast({ message, onDismiss }: ToastProps) {
  const { t } = useTranslation();
  useEffect(() => {
    const timeout = setTimeout(onDismiss, 4000);
    return () => clearTimeout(timeout);
  }, [onDismiss]);

  return (
    <div className={styles.toast} role="status">
      <span>{message}</span>
      <button className={styles.dismiss} aria-label={t("common.close")} onClick={onDismiss}>
        ✕
      </button>
    </div>
  );
}
