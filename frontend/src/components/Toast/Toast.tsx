import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { X } from "lucide-react";
import styles from "./Toast.module.css";

interface ToastProps {
  message: string;
  onDismiss: () => void;
}

// Save confirmation (screen 1h), also used in 1e for "Progress saved."
// Top right on desktop, bottom above the safe area on mobile (see the wireframe annotation on 1h),
// auto-dismiss after ~4s.
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
        <X size={16} />
      </button>
    </div>
  );
}
