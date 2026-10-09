import { useId, useState, type ChangeEvent, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Info } from "lucide-react";
import styles from "./InfoTip.module.css";

// Explanations sit behind a small (i) next to the label or heading they explain, instead of always
// showing under every field — the dashboard read as a wall of text. Opened by tap/click (not hover:
// tablets have none) and shown inline below the label, so it can't be clipped by a card or run off
// a narrow screen the way a floating bubble could. Warnings and "do this first" notes are not for
// this: they stay visible as a Callout or hint.

/** Open state plus the id that ties the (i) button to its panel. */
export function useInfoTip() {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  return { open, panelId, toggle: () => setOpen((value) => !value) };
}

interface InfoButtonProps {
  /** What the explanation is about — becomes "More about …" for screen readers. */
  topic: string;
  open: boolean;
  panelId: string;
  onToggle: () => void;
}

export function InfoButton({ topic, open, panelId, onToggle }: InfoButtonProps) {
  const { t } = useTranslation();
  return (
    <button
      type="button"
      className={`${styles.button} ${open ? styles.buttonOpen : ""}`}
      aria-label={t("common.moreInfo", { topic })}
      title={t("common.moreInfo", { topic })}
      aria-expanded={open}
      aria-controls={panelId}
      onClick={onToggle}
    >
      <Info size={15} strokeWidth={2} />
    </button>
  );
}

export function InfoPanel({ id, open, children }: { id: string; open: boolean; children: ReactNode }) {
  if (!open) return null;
  return (
    <div id={id} className={styles.panel}>
      {children}
    </div>
  );
}

interface LabelWithInfoProps {
  label: string;
  htmlFor?: string;
  /** Optional, so a caller can pass a condition-dependent explanation without branching. */
  info?: ReactNode;
  className?: string;
}

/** A form label with an (i) after it; the explanation opens below the label. */
export function LabelWithInfo({ label, htmlFor, info, className }: LabelWithInfoProps) {
  const tip = useInfoTip();
  return (
    <>
      <span className={styles.row}>
        <label htmlFor={htmlFor} className={className}>
          {label}
        </label>
        {info && <InfoButton topic={label} open={tip.open} panelId={tip.panelId} onToggle={tip.toggle} />}
      </span>
      {info && (
        <InfoPanel id={tip.panelId} open={tip.open}>
          {info}
        </InfoPanel>
      )}
    </>
  );
}

interface HeadingWithInfoProps {
  as?: "h2" | "h3" | "h4";
  title: string;
  info?: ReactNode;
  className?: string;
}

/** A section or page heading with an (i) after it, replacing an always-visible intro paragraph. */
export function HeadingWithInfo({ as: Heading = "h3", title, info, className }: HeadingWithInfoProps) {
  const tip = useInfoTip();
  return (
    <div className={className}>
      <div className={styles.row}>
        <Heading className={styles.heading}>{title}</Heading>
        {info && <InfoButton topic={title} open={tip.open} panelId={tip.panelId} onToggle={tip.toggle} />}
      </div>
      {info && (
        <InfoPanel id={tip.panelId} open={tip.open}>
          {info}
        </InfoPanel>
      )}
    </div>
  );
}

interface ToggleWithInfoProps {
  title: string;
  checked: boolean;
  onChange: (event: ChangeEvent<HTMLInputElement>) => void;
  info?: ReactNode;
  disabled?: boolean;
}

/** Checkbox + title, with the description behind an (i). The (i) sits outside the <label>: a button
 * inside a label is invalid HTML and would fight the label over the click. */
export function ToggleWithInfo({ title, checked, onChange, info, disabled }: ToggleWithInfoProps) {
  const tip = useInfoTip();
  return (
    <div className={styles.toggle}>
      <div className={styles.row}>
        <label className={styles.toggleLabel}>
          <input type="checkbox" checked={checked} onChange={onChange} disabled={disabled} />
          <strong>{title}</strong>
        </label>
        {info && <InfoButton topic={title} open={tip.open} panelId={tip.panelId} onToggle={tip.toggle} />}
      </div>
      {info && (
        <InfoPanel id={tip.panelId} open={tip.open}>
          {info}
        </InfoPanel>
      )}
    </div>
  );
}
