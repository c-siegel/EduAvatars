import { useId, type InputHTMLAttributes, type ReactNode } from "react";
import { LabelWithInfo } from "@/components/InfoTip";
import styles from "./Input.module.css";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  /** Explanation behind an (i) next to the label (see components/InfoTip). */
  info?: ReactNode;
}

export function Input({ label, info, id, className, ...props }: InputProps) {
  // Auto-generate an id when the caller doesn't supply one, so label/input stay linked.
  const generatedId = useId();
  const inputId = id ?? generatedId;

  return (
    <div className={styles.field}>
      <LabelWithInfo label={label} htmlFor={inputId} info={info} className={styles.label} />
      <input id={inputId} className={[styles.input, className].filter(Boolean).join(" ")} {...props} />
    </div>
  );
}
