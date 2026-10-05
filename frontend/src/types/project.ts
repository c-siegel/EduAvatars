export type ProjectStatus = "draft" | "published";

export interface Project {
  id: string;
  title: string;
  description: string | null;
  status: ProjectStatus;
  // Referenz auf den im API-Dashboard eingerichteten Schlüssel — die eigentliche Modellwahl.
  llmApiKeyId: string | null;
  // Vom Backend daraus abgeleiteter litellm-Modellstring (nur lesend, u.a. für Projektkarten und
  // den Modellfilter der Auswertung).
  llmModel: string | null;
  preprompt: string;
  // Erste Nachricht des Avatars, Schüler:innen sichtbar UND dem Modell als Kontext mitgegeben
  // (siehe backend features/ai/llm/__init__.py::complete). Leer = generische Begrüßung.
  startPrompt: string;
  // URL of the once-generated audio for startPrompt, or null if it hasn't been generated (yet)
  // — see the "Generate audio" button in Step3Behavior and pages/PublicChat/index.tsx's autoplay.
  startAudioUrl: string | null;
  // The avatar: one of the user's own library models (avatarModelId), or a bundled default avatar
  // by name (builtinAvatar, e.g. "julia" for public/avatars/julia.glb). Neither = default avatar.
  avatarModelId: string | null;
  builtinAvatar: string | null;
  avatarBackgroundId: string | null;
  // Ready-to-load URLs derived by the backend from the references above (read-only).
  avatarModelUrl: string | null;
  avatarBackgroundUrl: string | null;
  gradeLevel: string | null;
  // Sampling-Parameter, 1:1 an den Anbieter durchgereicht (siehe backend features/ai/llm
  // ::_sampling_params). temperature 0.0-2.0, topP 0.0-1.0 — dieselben Grenzen prüft das Backend.
  temperature: number;
  topP: number;
  published: boolean;
  shareSlug: string | null;
  saveConversations: boolean;
  surveyBeforeUrl: string | null;
  surveyBeforeEnabled: boolean;
  surveyAfterUrl: string | null;
  surveyAfterEnabled: boolean;
  ttsEnabled: boolean;
  // Referenz auf einen Key vom Typ TTS (analog llmApiKeyId).
  ttsApiKeyId: string | null;
  ttsVoice: string | null;
  // A clip from the owner's voice library (Dashboard → Voices) that local TTS clones the voice
  // from — only used while ttsApiKeyId is null. null speaks with the default local voice.
  ttsVoiceClipId: string | null;
  spokenLanguage: SpokenLanguage;
  // Reference to a key of type STT (mirrors ttsApiKeyId) — null keeps transcribing locally
  // (see backend features/ai/stt).
  sttApiKeyId: string | null;
  sttEnabled: boolean;
  // Whether this project prefers on-device (browser, WebGPU) transcription over sttApiKeyId/the
  // server's local Whisper — only shown/usable in the Configurator when the deployment also
  // allows it (see useBrowserSttStatus in lib/providers.ts).
  sttBrowserEnabled: boolean;
  // Whether the public chat should use sentence-chunked streaming (text+audio per sentence)
  // instead of waiting for the full reply — see backend features/chat/public_router.py's /messages/stream.
  // Meaningless without ttsEnabled, so the configurator only shows this toggle when TTS is on.
  streamingEnabled: boolean;
  // Ob der öffentliche Chat standardmäßig offen (true) oder eingeklappt-aber-ausklappbar (false)
  // startet. Wird im Konfigurator gesetzt/gespeichert; die Public-Chat-Seite rendert den
  // eingeklappten Zustand aktuell noch nicht (folgt später).
  chatDefaultOpen: boolean;
  // Whether a visitor must enter a password before the public chat unlocks (see
  // pages/PublicChat/index.tsx). The password itself is write-only — set/change/remove it via
  // projectsApi.update's separate `chatPassword` field, never read back here.
  passwordProtected: boolean;
  // Whether a visitor must type a name or ID before the public chat starts (see
  // pages/PublicChat/index.tsx's "name-gate" stage) — the entered value shows up next to that
  // visitor's saved conversation in the analytics export, but only if saveConversations is also on.
  requireVisitorName: boolean;
  createdAt: string;
}

// What projectsApi.update accepts: every writable field, plus the write-only chat password. The
// derived URLs (and llmModel) are computed server-side and never sent.
export type ProjectUpdate = Partial<
  Omit<Project, "avatarModelUrl" | "avatarBackgroundUrl" | "startAudioUrl" | "llmModel" | "passwordProtected">
> & { chatPassword?: string | null };

export type SpokenLanguage = "de" | "en";

export interface ProjectStats {
  totalProjects: number;
  publishedProjects: number;
  sessionsLast7Days: number;
  messagesLast7Days: number;
}
