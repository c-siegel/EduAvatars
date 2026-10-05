import type { SpokenLanguage } from "@/types/project";

// Lokaler Assistenten-Zustand für Screen 1e.
export interface ConfiguratorDraft {
  title: string;
  description: string;
  // See Project in types/project.ts — library avatar, bundled avatar, or neither (default).
  avatarModelId: string | null;
  builtinAvatar: string | null;
  avatarBackgroundId: string | null;
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
  sttBrowserEnabled: boolean;
  streamingEnabled: boolean;
}

export interface StepProps {
  draft: ConfiguratorDraft;
  onChange: (patch: Partial<ConfiguratorDraft>) => void;
}
