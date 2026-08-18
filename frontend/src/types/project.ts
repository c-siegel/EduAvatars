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
  avatarModelUrl: string | null;
  avatarBackgroundUrl: string | null;
  gradeLevel: string | null;
  creativity: number;
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
  sttEnabled: boolean;
  // Ob der öffentliche Chat standardmäßig offen (true) oder eingeklappt-aber-ausklappbar (false)
  // startet. Wird im Konfigurator gesetzt/gespeichert; die Public-Chat-Seite rendert den
  // eingeklappten Zustand aktuell noch nicht (folgt später).
  chatDefaultOpen: boolean;
  createdAt: string;
}

export type SpokenLanguage = "de" | "en";

export interface ProjectStats {
  totalProjects: number;
  publishedProjects: number;
  sessionsLast7Days: number;
  messagesLast7Days: number;
}
