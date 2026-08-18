import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Callout } from "@/components/Callout";
import { Input } from "@/components/Input";
import { apiKeysApi } from "@/api/apiKeys";
import { findProvider, keyDisplayName, modelLabel, useProviders } from "@/lib/providers";
import { SPOKEN_LANGUAGE_OPTIONS } from "@/lib/speechOptions";
import type { StepProps } from "../types";
import styles from "./shared.module.css";

// Platzhalter, solange noch kein Schlüssel gewählt wurde — ein <select> braucht immer einen
// kontrollierten String-Wert, draft.llmApiKeyId ist aber null, bis die Lehrkraft wählt.
const NO_MODEL_SELECTED = "";

// Schritt 2 — Technik: Modell, Kreativität, Sprache, TTS und STT.
export function Step2Technical({ draft, onChange }: StepProps) {
  // Zur Auswahl stehen ausschließlich tatsächlich eingerichtete Schlüssel vom Typ LLM (Screen 1g).
  // Vorher listete das Dropdown eine feste Modell-Liste, was Verfügbarkeit suggerierte, die erst
  // nach dem Hinterlegen eines passenden Keys bestand — der Fehler fiel dann erst im Chat auf.
  const providersQuery = useProviders();
  const keysQuery = useQuery({ queryKey: ["api-keys"], queryFn: apiKeysApi.list });
  const specs = providersQuery.data ?? [];
  const llmKeys = (keysQuery.data ?? []).filter((key) => key.keyType === "llm" && key.modelId);
  // TTS wählt wie das LLM-Modell direkt einen eingerichteten Key (Screen 1g), keine feste
  // Anbieter-Liste mehr — deckt damit automatisch jeden Anbieter ab, den die Registry für TTS
  // vorsieht (OpenAI, Gemini, Cartesia, eigener OpenAI-kompatibler Endpunkt).
  // Anbieter mit fest verdrahtetem TTS-Modell (ttsModelFixed) speichern bewusst kein modelId
  // (siehe ApiKeyForm.tsx) — die brauchen hier trotzdem als wählbar zu gelten.
  const ttsKeys = (keysQuery.data ?? []).filter((key) => {
    if (key.keyType !== "tts") return false;
    if (key.modelId) return true;
    return Boolean(findProvider(specs, key.provider)?.ttsModelFixed);
  });
  const keysLoaded = keysQuery.isSuccess && providersQuery.isSuccess;
  const hasNoModels = keysLoaded && llmKeys.length === 0;
  const hasNoTtsKeys = keysLoaded && ttsKeys.length === 0;

  return (
    <>
      <div className={styles.field}>
        <label className={styles.label} htmlFor="llm-model">
          Modell
        </label>
        {hasNoModels ? (
          <Callout variant="warning">
            Noch kein LLM eingerichtet. Lege zuerst unter{" "}
            <Link to="/dashboard/api">API-Schlüssel</Link> einen Schlüssel vom Typ LLM an — dort
            wählst du auch das Modell, das hier zur Verfügung stehen soll.
          </Callout>
        ) : (
          <>
            <select
              id="llm-model"
              className={styles.select}
              value={draft.llmApiKeyId ?? NO_MODEL_SELECTED}
              onChange={(e) => onChange({ llmApiKeyId: e.target.value || null })}
              disabled={!keysLoaded}
            >
              <option value={NO_MODEL_SELECTED}>Bitte wählen …</option>
              {llmKeys.map((key) => (
                <option key={key.id} value={key.id}>
                  {keyDisplayName(key, specs)} · {modelLabel(key, specs)}
                </option>
              ))}
            </select>
            <p className={styles.hint}>
              Es stehen nur Modelle zur Wahl, für die du unter API-Schlüssel einen Zugang
              eingerichtet hast. Ein weiteres Modell fügst du dort als neuen Schlüssel hinzu.
            </p>
          </>
        )}
      </div>

      <div className={styles.field}>
        <label className={styles.label} htmlFor="creativity">
          Kreativität
        </label>
        <div className={styles.sliderRow}>
          <input
            id="creativity"
            type="range"
            min={0}
            max={1}
            step={0.1}
            value={draft.creativity}
            onChange={(e) => onChange({ creativity: Number(e.target.value) })}
          />
          <span className={styles.sliderValue}>{draft.creativity.toFixed(1)}</span>
        </div>
      </div>

      <div className={styles.field}>
        <label className={styles.label} htmlFor="spoken-language">
          Sprache
        </label>
        <select
          id="spoken-language"
          className={styles.select}
          value={draft.spokenLanguage}
          onChange={(e) => onChange({ spokenLanguage: e.target.value as typeof draft.spokenLanguage })}
        >
          {SPOKEN_LANGUAGE_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <p className={styles.hint}>
          Bestimmt die Antwortsprache und die Spracherkennung des Avatars.
        </p>
      </div>

      <label className={styles.toggleRow}>
        <input
          type="checkbox"
          checked={draft.ttsEnabled}
          onChange={(e) => onChange({ ttsEnabled: e.target.checked })}
        />
        <span className={styles.toggleCopy}>
          <strong>Sprachausgabe (TTS)</strong>
          <span>Der Avatar spricht seine Antworten laut vor. Standardmäßig aus.</span>
        </span>
      </label>

      {draft.ttsEnabled && (
        <div className={styles.field}>
          <label className={styles.label} htmlFor="tts-key">
            TTS-Schlüssel
          </label>
          {hasNoTtsKeys ? (
            <Callout variant="warning">
              Noch kein TTS eingerichtet. Lege zuerst unter{" "}
              <Link to="/dashboard/api">API-Schlüssel</Link> einen Schlüssel vom Typ TTS an (z. B.
              OpenAI, Google Gemini, Cartesia oder ein eigener Endpunkt).
            </Callout>
          ) : (
            <>
              <select
                id="tts-key"
                className={styles.select}
                value={draft.ttsApiKeyId ?? NO_MODEL_SELECTED}
                onChange={(e) => onChange({ ttsApiKeyId: e.target.value || null })}
                disabled={!keysLoaded}
              >
                <option value={NO_MODEL_SELECTED}>Bitte wählen …</option>
                {ttsKeys.map((key) => (
                  <option key={key.id} value={key.id}>
                    {keyDisplayName(key, specs)} · {modelLabel(key, specs)}
                  </option>
                ))}
              </select>
              <Input
                label="Stimme (optional)"
                placeholder="z. B. alloy — abhängig vom gewählten Anbieter"
                value={draft.ttsVoice}
                onChange={(e) => onChange({ ttsVoice: e.target.value })}
              />
              <p className={styles.hint}>
                Für Cartesia ist eine Stimme Pflicht (kein Standardwert) — ohne läuft die
                Sprachausgabe für dieses Projekt ins Leere.
              </p>
            </>
          )}
        </div>
      )}

      <label className={styles.toggleRow}>
        <input
          type="checkbox"
          checked={draft.sttEnabled}
          onChange={(e) => onChange({ sttEnabled: e.target.checked })}
        />
        <span className={styles.toggleCopy}>
          <strong>Spracheingabe (STT)</strong>
          <span>Aktiviert den Mikrofon-Button im öffentlichen Chat. Standardmäßig aus.</span>
        </span>
      </label>
    </>
  );
}
