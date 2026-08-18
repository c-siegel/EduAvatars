export type ApiKeyStatus = "active" | "unverified" | "error";

// Wofür ein Schlüssel eingerichtet ist.
export type ApiKeyType = "llm" | "tts";

export const KEY_TYPE_LABELS: Record<ApiKeyType, string> = {
  llm: "LLM",
  tts: "TTS",
};

// Generischer Anbieter für alles, was die OpenAI-API nachbildet (früher der Sonderfall "custom").
export const OPENAI_COMPATIBLE_PROVIDER = "openai_compatible";

export interface ApiKey {
  id: string;
  provider: string;
  keyType: ApiKeyType;
  label: string | null;
  maskedKey: string;
  addedAt: string;
  status: ApiKeyStatus;
  apiBase: string | null;
  modelId: string | null;
  arcanaId: string | null;
  usedByProjects: number;
}

export interface ApiKeyInput {
  provider: string;
  keyType: ApiKeyType;
  label: string | null;
  // Beim Bearbeiten heißt leer: gespeicherten Schlüssel unverändert lassen.
  apiKey: string;
  apiBase: string | null;
  modelId: string | null;
  arcanaId: string | null;
}

export interface ProviderModel {
  value: string;
  label: string;
}

// Anbieter-Stammdaten aus der Backend-Registry (app/core/providers.py) — Vorbelegungen, Pflichtfelder
// und kuratierte Modelle werden nicht im Frontend gepflegt, damit beide Seiten nicht auseinanderlaufen.
export interface ProviderSpec {
  value: string;
  label: string;
  keyPlaceholder: string;
  defaultApiBase: string | null;
  apiBaseRequired: boolean;
  keyRequired: boolean;
  supportedTypes: ApiKeyType[];
  models: ProviderModel[];
  hint: string | null;
  // Sprachausgabe-Modell steht bei diesem Anbieter fest (z. B. OpenAI/Gemini) — das Modellfeld
  // wird für TTS-Keys dann ausgeblendet, statt eine Auswahl zu erzwingen, die nie verwendet wird.
  ttsModelFixed: boolean;
  // Zusätzliches Pflichtfeld "Arcana-ID" im Key-Formular (aktuell nur GWDG Arcana).
  requiresArcanaId: boolean;
}
