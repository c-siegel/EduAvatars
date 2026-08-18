import { useQuery } from "@tanstack/react-query";
import { apiKeysApi } from "@/api/apiKeys";
import type { ApiKey, ProviderSpec } from "@/types/apiKey";

// Anbieter, Endpunkt-Vorbelegungen und kuratierte Modelle kommen aus der Backend-Registry
// (backend/app/core/providers.py) statt aus einer zweiten Liste hier — sonst kann das Frontend
// Anbieter oder Modelle anbieten, für die es serverseitig keinen Aufrufpfad gibt.
export function useProviders() {
  return useQuery({
    queryKey: ["api-key-providers"],
    queryFn: apiKeysApi.listProviders,
    // Stammdaten ändern sich nur mit einem Deployment.
    staleTime: Infinity,
  });
}

export function findProvider(specs: ProviderSpec[], value: string): ProviderSpec | undefined {
  return specs.find((spec) => spec.value === value);
}

export function providerLabel(specs: ProviderSpec[], value: string): string {
  return findProvider(specs, value)?.label ?? value;
}

/** Anzeigename eines Schlüssels: der individuelle Name der Lehrkraft, sonst das Anbieter-Label. */
export function keyDisplayName(key: ApiKey, specs: ProviderSpec[]): string {
  return key.label?.trim() || providerLabel(specs, key.provider);
}

/** Anzeigename des hinterlegten Modells — kuratierter Titel, sonst die eingetragene Modell-ID. */
export function modelLabel(key: ApiKey, specs: ProviderSpec[]): string | null {
  const spec = findProvider(specs, key.provider);
  if (!key.modelId) {
    // TTS-Anbieter mit fest verdrahtetem Sprachausgabe-Modell (OpenAI/Gemini) speichern bewusst
    // kein model_id (siehe ApiKeyForm.tsx) — kein "kein Modell", sondern schlicht keine Wahl nötig.
    return key.keyType === "tts" && spec?.ttsModelFixed ? "Standardmodell" : null;
  }
  return spec?.models.find((model) => model.value === key.modelId)?.label ?? key.modelId;
}
