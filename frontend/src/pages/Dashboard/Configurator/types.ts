import type { SpokenLanguage } from "@/types/project";

// Lokaler Assistenten-Zustand für Screen 1e.
export interface ConfiguratorDraft {
  title: string;
  description: string;
  avatarModelUrl: string | null;
  avatarBackgroundUrl: string | null;
  chatDefaultOpen: boolean;
  gradeLevel: string;
  preprompt: string;
  startPrompt: string;
  // Die Modellwahl läuft über den eingerichteten Schlüssel (Screen 1g); null = noch keiner gewählt.
  llmApiKeyId: string | null;
  temperature: number;
  topP: number;
  saveConversations: boolean;
  requireVisitorName: boolean;
  surveyBeforeUrl: string;
  surveyBeforeEnabled: boolean;
  surveyAfterUrl: string;
  surveyAfterEnabled: boolean;
  spokenLanguage: SpokenLanguage;
  ttsEnabled: boolean;
  ttsApiKeyId: string | null;
  ttsVoice: string;
  sttApiKeyId: string | null;
  sttEnabled: boolean;
  streamingEnabled: boolean;
}

export interface StepProps {
  draft: ConfiguratorDraft;
  onChange: (patch: Partial<ConfiguratorDraft>) => void;
}
