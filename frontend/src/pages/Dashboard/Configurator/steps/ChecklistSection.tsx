// Configurator step 3, "Conversation plan": steps the avatar works through and ticks off during
// the chat (see backend features/chat/checklist.py), optionally visible to students.

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ArrowDown, ArrowUp, NotebookPen, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/Button";
import { Callout } from "@/components/Callout";
import { InfoButton, InfoPanel, ToggleWithInfo, useInfoTip } from "@/components/InfoTip";
import { newChecklistId } from "@/lib/checklist";
import type { ChecklistItem } from "@/types/project";
import type { StepProps } from "../types";
import styles from "./ChecklistSection.module.css";

// Same caps as the backend (features/projects/schemas.py).
const MAX_ITEMS = 20;
const MAX_TITLE_LENGTH = 120;
const MAX_NOTE_LENGTH = 1000;

export function ChecklistSection({ draft, onChange }: StepProps) {
  const { t } = useTranslation();
  const introTip = useInfoTip();
  const items = draft.checklistItems;
  // Steps whose note field is shown — at first the ones that have a note. Hiding a note keeps it.
  const [openNotes, setOpenNotes] = useState<Set<string>>(
    () => new Set(items.filter((item) => item.note).map((item) => item.id)),
  );

  function setItems(next: ChecklistItem[]) {
    onChange({ checklistItems: next });
  }

  function updateItem(index: number, patch: Partial<ChecklistItem>) {
    setItems(items.map((item, i) => (i === index ? { ...item, ...patch } : item)));
  }

  function moveItem(index: number, delta: -1 | 1) {
    const next = [...items];
    [next[index], next[index + delta]] = [next[index + delta], next[index]];
    setItems(next);
  }

  function addItem() {
    setItems([...items, { id: newChecklistId(), title: "", note: null }]);
  }

  function toggleNote(id: string) {
    setOpenNotes((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <section className={styles.section} aria-labelledby="checklist-section-title">
      <div className={styles.titleRow}>
        <h3 id="checklist-section-title" className={styles.title}>
          {t("configurator.checklist.title")}
        </h3>
        <InfoButton
          topic={t("configurator.checklist.title")}
          open={introTip.open}
          panelId={introTip.panelId}
          onToggle={introTip.toggle}
        />
      </div>
      <InfoPanel id={introTip.panelId} open={introTip.open}>
        {t("configurator.checklist.intro")}
      </InfoPanel>

      <ToggleWithInfo
        title={t("configurator.checklist.enabled")}
        checked={draft.checklistEnabled}
        onChange={(e) => onChange({ checklistEnabled: e.target.checked })}
      />

      {draft.checklistEnabled && (
        <>
          <div className={styles.orders} role="radiogroup" aria-label={t("configurator.checklist.orderLabel")}>
            {[true, false].map((ordered) => (
              <label key={String(ordered)} className={styles.order}>
                <input
                  type="radio"
                  name="checklist-order"
                  checked={draft.checklistOrdered === ordered}
                  onChange={() => onChange({ checklistOrdered: ordered })}
                />
                <span>
                  <strong>{t(ordered ? "configurator.checklist.ordered" : "configurator.checklist.anyOrder")}</strong>
                  <span className={styles.hint}>
                    {t(ordered ? "configurator.checklist.orderedHint" : "configurator.checklist.anyOrderHint")}
                  </span>
                </span>
              </label>
            ))}
          </div>

          <ToggleWithInfo
            title={t("configurator.checklist.visible")}
            checked={draft.checklistVisible}
            onChange={(e) => onChange({ checklistVisible: e.target.checked })}
            info={t("configurator.checklist.visibleHint")}
          />

          <ol className={styles.items}>
            {items.map((item, index) => {
              const noteOpen = openNotes.has(item.id);
              const number = index + 1;
              return (
                <li key={item.id} className={styles.item}>
                  <div className={styles.itemRow}>
                    <span className={styles.number} aria-hidden="true">
                      {number}.
                    </span>
                    <input
                      className={styles.titleInput}
                      value={item.title}
                      maxLength={MAX_TITLE_LENGTH}
                      placeholder={t("configurator.checklist.stepPlaceholder")}
                      aria-label={t("configurator.checklist.stepTitle", { number })}
                      onChange={(e) => updateItem(index, { title: e.target.value })}
                    />
                    <div className={styles.itemActions}>
                      <button
                        type="button"
                        className={styles.iconButton}
                        aria-pressed={noteOpen}
                        aria-label={t("configurator.checklist.noteToggle", { number })}
                        title={t("configurator.checklist.noteToggle", { number })}
                        onClick={() => toggleNote(item.id)}
                      >
                        <NotebookPen size={16} />
                      </button>
                      <button
                        type="button"
                        className={styles.iconButton}
                        disabled={index === 0}
                        aria-label={t("configurator.checklist.moveUp", { number })}
                        title={t("configurator.checklist.moveUp", { number })}
                        onClick={() => moveItem(index, -1)}
                      >
                        <ArrowUp size={16} />
                      </button>
                      <button
                        type="button"
                        className={styles.iconButton}
                        disabled={index === items.length - 1}
                        aria-label={t("configurator.checklist.moveDown", { number })}
                        title={t("configurator.checklist.moveDown", { number })}
                        onClick={() => moveItem(index, 1)}
                      >
                        <ArrowDown size={16} />
                      </button>
                      <button
                        type="button"
                        className={styles.iconButton}
                        aria-label={t("configurator.checklist.remove", { number })}
                        title={t("configurator.checklist.remove", { number })}
                        onClick={() => setItems(items.filter((_, i) => i !== index))}
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>
                  {noteOpen && (
                    <textarea
                      className={styles.noteInput}
                      value={item.note ?? ""}
                      maxLength={MAX_NOTE_LENGTH}
                      rows={2}
                      placeholder={t("configurator.checklist.notePlaceholder")}
                      aria-label={t("configurator.checklist.noteLabel", { number })}
                      onChange={(e) => updateItem(index, { note: e.target.value })}
                    />
                  )}
                </li>
              );
            })}
          </ol>

          {items.length === 0 && <Callout variant="info">{t("configurator.checklist.empty")}</Callout>}
          <div>
            <Button size="sm" onClick={addItem} disabled={items.length >= MAX_ITEMS}>
              <Plus size={14} /> {t("configurator.checklist.add")}
            </Button>
          </div>
        </>
      )}
    </section>
  );
}
