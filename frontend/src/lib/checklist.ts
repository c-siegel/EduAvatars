// Conversation plan helpers shared by the configurator, the preview and the public chat (see
// backend features/chat/checklist.py for how the avatar ticks steps off).

import type { ChecklistCheck } from "@/types/chat";
import type { ChecklistItem } from "@/types/project";

// Matches the backend's CHECKLIST_ID_PATTERN (lowercase hex is a subset of it). getRandomValues
// instead of randomUUID: the latter only exists in secure contexts, and a self-hosted instance
// may be reached over plain http on a school network.
export function newChecklistId(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(4));
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

// The steps as the backend stores them: trimmed, a blank note as null, steps without a title
// dropped (an "Add step" row the teacher never filled in). Used both for saving and for the
// unsaved-changes comparison, so a trailing space doesn't count as a change.
export function normalizeChecklist(items: ChecklistItem[]): ChecklistItem[] {
  return items
    .map((item) => ({ id: item.id, title: item.title.trim(), note: item.note?.trim() || null }))
    .filter((item) => item.title);
}

// The IDs of the steps done after applying every message's ticks in order — the same replay the
// backend does on each turn, so what students see matches what the model was told.
export function doneStepIds(messages: { checks?: ChecklistCheck[] }[]): Set<string> {
  const done = new Set<string>();
  for (const message of messages) {
    for (const check of message.checks ?? []) {
      if (check.done) done.add(check.id);
      else done.delete(check.id);
    }
  }
  return done;
}
