// The conversation plan as students (and the teacher in the preview) see it: a small collapsible
// card listing the steps, with the ones the avatar ticked off (see backend
// features/chat/checklist.py). Progress comes in as `doneIds`, derived from the messages, so it
// rolls back with an edited or regenerated message without any state of its own.

import { useEffect, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Check, ChevronDown, ChevronUp, ListChecks } from "lucide-react";
import styles from "./ChecklistCard.module.css";

interface ChecklistCardProps {
  items: { id: string; title: string }[];
  ordered: boolean;
  doneIds: Set<string>;
  // "overlay" floats over the avatar stage; "inline" sits in normal flow (chat-only layout, preview).
  variant?: "overlay" | "inline";
  className?: string;
}

// On a phone the avatar stage is small, so the card starts collapsed there and leaves the face free.
function startsExpanded(): boolean {
  return typeof window === "undefined" || window.matchMedia("(min-width: 900px)").matches;
}

export function ChecklistCard({ items, ordered, doneIds, variant = "overlay", className }: ChecklistCardProps) {
  const { t } = useTranslation();
  const listId = useId();
  const [expanded, setExpanded] = useState(startsExpanded);
  const [announcement, setAnnouncement] = useState("");
  const previousDone = useRef(doneIds);

  // Tells screen-reader users when a step is ticked off or taken back — the visual change alone
  // happens silently while the avatar speaks.
  useEffect(() => {
    const before = previousDone.current;
    previousDone.current = doneIds;
    const ticked = items.filter((item) => doneIds.has(item.id) && !before.has(item.id));
    const unticked = items.filter((item) => !doneIds.has(item.id) && before.has(item.id));
    const parts = [
      ...ticked.map((item) => t("checklist.stepDone", { title: item.title })),
      ...unticked.map((item) => t("checklist.stepUndone", { title: item.title })),
    ];
    if (parts.length) setAnnouncement(parts.join(" "));
  }, [doneIds, items, t]);

  const doneCount = items.filter((item) => doneIds.has(item.id)).length;
  const nextId = ordered ? items.find((item) => !doneIds.has(item.id))?.id : undefined;

  return (
    <section
      className={[styles.card, variant === "overlay" ? styles.overlay : styles.inline, className].filter(Boolean).join(" ")}
      aria-label={t("checklist.title")}
    >
      <button
        type="button"
        className={styles.header}
        aria-expanded={expanded}
        aria-controls={listId}
        onClick={() => setExpanded(!expanded)}
      >
        <ListChecks size={16} aria-hidden="true" />
        <span className={styles.title}>{t("checklist.title")}</span>
        <span className={styles.progress}>
          {doneCount === items.length
            ? t("checklist.allDone")
            : t("checklist.progress", { done: doneCount, total: items.length })}
        </span>
        {expanded ? <ChevronUp size={16} aria-hidden="true" /> : <ChevronDown size={16} aria-hidden="true" />}
      </button>
      <ol id={listId} className={styles.list} hidden={!expanded}>
        {items.map((item) => {
          const done = doneIds.has(item.id);
          return (
            <li
              key={item.id}
              className={[styles.item, done && styles.done, item.id === nextId && styles.next].filter(Boolean).join(" ")}
              aria-current={item.id === nextId ? "step" : undefined}
            >
              <span className={styles.box} aria-hidden="true">
                {done && <Check size={12} strokeWidth={3} />}
              </span>
              <span className={styles.itemTitle}>{item.title}</span>
              <span className={styles.srOnly}>{done ? t("checklist.done") : t("checklist.open")}</span>
            </li>
          );
        })}
      </ol>
      <p className={styles.srOnly} aria-live="polite">
        {announcement}
      </p>
    </section>
  );
}
