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
  // (siehe backend services/llm_service.py::send_chat_message). Leer = generische Begrüßung.
  startPrompt: string;
  // Route to the once-generated audio for startPrompt, or null if it hasn't been generated (yet)
  // — see the "Generate audio" button in Step3Behavior and pages/PublicChat/index.tsx's autoplay.
  startAudioUrl: string | null;
  avatarModelUrl: string | null;
  avatarBackgroundUrl: string | null;
  gradeLevel: string | null;
  // Sampling-Parameter, 1:1 an den Anbieter durchgereicht (siehe backend services/llm_service.py
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
  spokenLanguage: SpokenLanguage;
  // Reference to a key of type STT (mirrors ttsApiKeyId) — null keeps transcribing locally
  // (see backend services/stt_service.py).
  sttApiKeyId: string | null;
  sttEnabled: boolean;
  // Whether the public chat should use sentence-chunked streaming (text+audio per sentence)
  // instead of waiting for the full reply — see backend api/public_chat.py's /message/stream.
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

export type SpokenLanguage = "de" | "en";

export interface ProjectStats {
  totalProjects: number;
  publishedProjects: number;
  sessionsLast7Days: number;
  messagesLast7Days: number;
}
