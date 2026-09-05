import { API_BASE_URL, apiClient, ApiError } from "./client";
import { getUnlockToken } from "@/lib/chatUnlockStorage";
import { getVisitorName } from "@/lib/visitorNameStorage";
import type { ChatMessage } from "@/types/chat";
import type { SpokenLanguage } from "@/types/project";

export interface PublicProject {
  title: string;
  teacherName: string;
  // Erste Nachricht des Avatars, dem Modell ebenfalls als Kontext mitgegeben (siehe Backend
  // services/llm_service.py::send_chat_message). Leer = generische Begrüßung im Frontend.
  startPrompt: string | null;
  // Route to the once-generated audio for startPrompt, or null if it hasn't been generated (yet)
  // — see pages/PublicChat/index.tsx's autoplay-on-load and overlay play button.
  startAudioUrl: string | null;
  avatarModelUrl: string | null;
  avatarBackgroundUrl: string | null;
  spokenLanguage: SpokenLanguage;
  ttsEnabled: boolean;
  sttEnabled: boolean;
  // See types/project.ts — the page only uses the streaming endpoint when this AND ttsEnabled
  // are both true (see pages/PublicChat/index.tsx).
  streamingEnabled: boolean;
  // Siehe types/project.ts — noch ohne UI-Auswirkung auf dieser Seite.
  chatDefaultOpen: boolean;
  surveyBeforeUrl: string | null;
  surveyAfterUrl: string | null;
  // Whether this chat requires a password, and whether this tab already unlocked it — see
  // pages/PublicChat/index.tsx's "locked" stage.
  passwordProtected: boolean;
  unlocked: boolean;
  // Whether a visitor must type a name/ID before the chat starts — see pages/PublicChat/index.tsx's
  // "name-gate" stage. Unlike passwordProtected/unlocked, whether it's already been entered lives
  // entirely in visitorNameStorage.ts, not in this response.
  requireVisitorName: boolean;
  // Shown to students so the page can be honest about what happens to what they type: whether the
  // conversation is recorded, and which AI model replies. Not used for any logic.
  saveConversations: boolean;
  llmModel: string | null;
}

// Attaches the stored unlock token (if any) so an already-unlocked tab stays unlocked across
// loadTutor/sendMessage/transcribe calls — the backend re-verifies it regardless, this header is
// just how the client proves it already passed the check once.
function unlockHeader(slug: string): Record<string, string> | undefined {
  const token = getUnlockToken(slug);
  return token ? { "X-Chat-Unlock-Token": token } : undefined;
}

// Attaches the visitor-entered name/ID (see visitorNameStorage.ts), if any — encoded because raw
// HTTP header values can't carry arbitrary Unicode (see visitor_name_service.py::clean_visitor_name
// on the backend, which decodes it again).
function visitorNameHeader(slug: string): Record<string, string> | undefined {
  const name = getVisitorName(slug);
  return name ? { "X-Visitor-Name": encodeURIComponent(name) } : undefined;
}

// Every public-chat request attaches both the chat-unlock token and the visitor name (whichever
// of the two are actually stored) — combined into one helper so a call site can't forget one.
function requestHeaders(slug: string): Record<string, string> {
  return { ...unlockHeader(slug), ...visitorNameHeader(slug) };
}

// One sentence-sized piece of the reply, text and audio together — see
// app/api/public_chat.py::send_message_stream's SSE (server-sent events) schema. Keys are already
// camelCase as sent by the backend (a plain dict there, not a CamelModel), so no conversion needed.
export interface StreamChunkEvent {
  index: number;
  text: string;
  audioBase64: string | null;
  contentType: string | null;
}

export interface StreamDoneEvent {
  reply: string;
  llmMs: number | null;
  firstChunkMs: number | null;
  // Time until the first chunk was handed to TTS — distinct from firstChunkMs, which is until
  // that chunk's synthesis *finishes*. Isolates LLM/chunking speed from TTS speed.
  firstChunkTextReadyMs: number | null;
  ttsMs: number | null;
}

interface StreamHandlers {
  onChunk: (chunk: StreamChunkEvent) => void;
  onDone: (data: StreamDoneEvent) => void;
}

/** Parses one "event: <name>\ndata: <json>" SSE frame (without the trailing blank line). */
function parseSseFrame(frame: string): { event: string; data: unknown } | null {
  let event = "message";
  let dataLine: string | null = null;
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) event = line.slice("event:".length).trim();
    else if (line.startsWith("data:")) dataLine = line.slice("data:".length).trim();
  }
  return dataLine == null ? null : { event, data: JSON.parse(dataLine) };
}

// EventSource can't be used here: it can only GET, and can't set the custom headers that
// requestHeaders() provides — so this reads the stream by hand via fetch + getReader() instead.
//
// Whether a caught failure should make the page fall back to the plain /message endpoint depends
// on whether any chunk already arrived: once part of the reply has been shown/spoken, retrying via
// the plain endpoint would ask the LLM again and could speak the answer twice. So this only throws
// (signalling "safe to fall back") for a failure before the first chunk; anything after that is
// swallowed and the (partial) reply already delivered is treated as the final one.
export async function sendMessageStream(
  slug: string,
  message: string,
  history: ChatMessage[],
  handlers: StreamHandlers,
  signal: AbortSignal,
): Promise<void> {
  let receivedAnyChunk = false;
  try {
    const res = await fetch(`${API_BASE_URL}/public/${slug}/message/stream`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", ...requestHeaders(slug) },
      body: JSON.stringify({ message, history }),
      signal,
    });
    if (!res.ok) {
      throw new ApiError(res.status, await res.text());
    }
    if (!res.body) {
      throw new Error("Streaming-Antwort hat keinen Body.");
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let separatorAt: number;
      while ((separatorAt = buffer.indexOf("\n\n")) !== -1) {
        const frame = buffer.slice(0, separatorAt);
        buffer = buffer.slice(separatorAt + 2);
        const parsed = parseSseFrame(frame);
        if (!parsed) continue;
        if (parsed.event === "chunk") {
          receivedAnyChunk = true;
          handlers.onChunk(parsed.data as StreamChunkEvent);
        } else if (parsed.event === "done") {
          handlers.onDone(parsed.data as StreamDoneEvent);
          return;
        } else if (parsed.event === "error") {
          if (receivedAnyChunk) return;
          const detail = (parsed.data as { detail: string }).detail;
          throw new ApiError(503, JSON.stringify({ detail }));
        }
      }
    }
  } catch (error) {
    // A user-initiated stop (see pages/PublicChat/index.tsx::interruptResponse) — never falls back
    // to the plain endpoint, unlike a genuine failure below, since the student explicitly ended it.
    if (error instanceof DOMException && error.name === "AbortError") return;
    if (receivedAnyChunk) return;
    throw error;
  }
}

export const publicChatApi = {
  loadTutor: (slug: string) => apiClient.get<PublicProject>(`/public/${slug}`, requestHeaders(slug)),
  unlock: (slug: string, password: string) =>
    apiClient.post<{ unlockToken: string }>(`/public/${slug}/unlock`, { password }),
  // Backend gibt {reply} zurück, keine vollständige Conversation (siehe app/api/public_chat.py) —
  // war zuvor fälschlich als Conversation typisiert.
  sendMessage: (slug: string, message: string, history: ChatMessage[], signal?: AbortSignal) =>
    // llmMs/ttsMs: backend-side call durations, only meaningful together with the client-side
    // timestamps captured in PublicChat/index.tsx's latency-test log (?latencyTest=1).
    apiClient.post<{
      reply: string;
      audioBase64: string | null;
      contentType: string | null;
      llmMs: number | null;
      ttsMs: number | null;
    }>(`/public/${slug}/message`, { message, history }, requestHeaders(slug), signal),
  sendMessageStream,
  // initialPrompt: text already transcribed earlier in the same recording (see the pause-triggered
  // segmentation in pages/PublicChat/index.tsx) — improves accuracy right at the segment seam.
  // Omitted for a plain single-shot recording, exactly like before this parameter existed.
  transcribe: (slug: string, audio: Blob, initialPrompt?: string) => {
    const formData = new FormData();
    formData.append("audio", audio, "recording.webm");
    if (initialPrompt) formData.append("initial_prompt", initialPrompt);
    return apiClient.upload<{ text: string; sttMs: number | null }>(
      `/public/${slug}/transcribe`,
      formData,
      requestHeaders(slug),
    );
  },
};
