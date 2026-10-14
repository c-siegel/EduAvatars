export interface ChatMessage {
  // "system" is a local-only UI notice (e.g. "response interrupted", see PublicChat/index.tsx) —
  // never sent to the backend, whose ChatHistoryEntry only accepts "user"/"assistant" (422s
  // otherwise). Always filter with toApiHistory() before handing a message list to the API.
  role: "user" | "assistant" | "system";
  content: string;
  // Conversation-plan steps the avatar ticked off or took back in this reply (see
  // lib/checklist.ts). Sent back with the history, so the backend can replay the progress.
  checks?: ChecklistCheck[];
}

export interface ChecklistCheck {
  id: string;
  done: boolean;
}
