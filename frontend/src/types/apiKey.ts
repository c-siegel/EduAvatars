export type ApiKeyStatus = "active" | "unverified" | "error";

// What a key is set up for.
export type ApiKeyType = "llm" | "tts" | "stt";

export const KEY_TYPE_LABELS: Record<ApiKeyType, string> = {
  llm: "LLM",
  tts: "TTS",
  stt: "STT",
};

// All key types, for the type selector in ApiKeyForm.tsx (shown before any provider is picked,
// so it can't be derived from a single provider's supportedTypes).
export const ALL_KEY_TYPES: ApiKeyType[] = ["llm", "tts", "stt"];

// Generic provider for anything that mimics the OpenAI API (formerly the special case "custom").
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
  // When editing, empty means: leave the stored key unchanged.
  apiKey: string;
  apiBase: string | null;
  modelId: string | null;
  arcanaId: string | null;
}

export interface ProviderModel {
  value: string;
  label: string;
}

// Provider reference data from the backend registry (app/core/providers.py) — defaults, required
// fields and curated models aren't maintained in the frontend, so the two sides can't drift apart.
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
  // The speech output model is fixed for this provider (e.g. OpenAI/Gemini) — the model field is
  // then hidden for TTS keys instead of forcing a choice that's never used.
  ttsModelFixed: boolean;
  // Same idea for STT keys (currently only GWDG SAIA, which has exactly one Whisper model).
  sttModelFixed: boolean;
  // Extra required field "Arcana ID" in the key form (currently only GWDG Arcana).
  requiresArcanaId: boolean;
}
