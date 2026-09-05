import { useId, type TextareaHTMLAttributes } from "react";
import styles from "./Input.module.css";

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string;
  hint?: string;
}

export function Textarea({ label, hint, id, className, ...props }: TextareaProps) {
  const generatedId = useId();
  const inputId = id ?? generatedId;

  return (
    <div className={styles.field}>
      <div className={styles.labelRow}>
        <label htmlFor={inputId} className={styles.label}>
          {label}
        </label>
        {hint && <span className={styles.hint}>{hint}</span>}
      </div>
      <textarea id={inputId} className={[styles.input, styles.textarea, className].filter(Boolean).join(" ")} {...props} />
    </div>
  );
}
