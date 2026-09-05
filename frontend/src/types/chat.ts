export interface ChatMessage {
  // "system" is a local-only UI notice (e.g. "response interrupted", see PublicChat/index.tsx) —
  // never sent to the backend, whose ChatHistoryEntry only accepts "user"/"assistant" (422s
  // otherwise). Always filter with toApiHistory() before handing a message list to the API.
  role: "user" | "assistant" | "system";
  content: string;
}
