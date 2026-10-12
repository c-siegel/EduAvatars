import { useId, type ReactNode, type TextareaHTMLAttributes } from "react";
import { InfoButton, InfoPanel, useInfoTip } from "@/components/InfoTip";
import styles from "./Input.module.css";

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string;
  hint?: string;
  /** Explanation behind an (i) next to the label (see components/InfoTip). */
  info?: ReactNode;
}

export function Textarea({ label, hint, info, id, className, ...props }: TextareaProps) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const tip = useInfoTip();

  return (
    <div className={styles.field}>
      <div className={styles.labelRow}>
        <span className={styles.labelWithInfo}>
          <label htmlFor={inputId} className={styles.label}>
            {label}
          </label>
          {info && <InfoButton topic={label} open={tip.open} panelId={tip.panelId} onToggle={tip.toggle} />}
        </span>
        {hint && <span className={styles.hint}>{hint}</span>}
      </div>
      {info && (
        <InfoPanel id={tip.panelId} open={tip.open}>
          {info}
        </InfoPanel>
      )}
      <textarea id={inputId} className={[styles.input, styles.textarea, className].filter(Boolean).join(" ")} {...props} />
    </div>
  );
}
