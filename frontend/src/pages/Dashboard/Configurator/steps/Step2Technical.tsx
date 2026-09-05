import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Callout } from "@/components/Callout";
import { Input } from "@/components/Input";
import { apiKeysApi } from "@/api/apiKeys";
import { findProvider, keyDisplayName, modelLabel, useProviders } from "@/lib/providers";
import { SPOKEN_LANGUAGE_VALUES } from "@/lib/speechOptions";
import type { StepProps } from "../types";
import styles from "./shared.module.css";

// Platzhalter, solange noch kein Schlüssel gewählt wurde — ein <select> braucht immer einen
// kontrollierten String-Wert, draft.llmApiKeyId ist aber null, bis die Lehrkraft wählt.
const NO_MODEL_SELECTED = "";

// Obergrenzen der beiden Sampling-Parameter — dieselben Werte prüft das Backend nochmal
// (MAX_TEMPERATURE/MAX_TOP_P in backend/app/models/schemas/project.py), damit ein per API
// gesetzter Wert nicht am Slider vorbeikommt.
const MAX_TEMPERATURE = 2;
const MAX_TOP_P = 1;

// Schritt 2 — Technik: Modell, Sampling (Temperatur/Top P), Sprache, TTS und STT.
export function Step2Technical({ draft, onChange }: StepProps) {
  const { t } = useTranslation();
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
  // STT (currently only GWDG SAIA) is optional — with no key selected, transcription keeps
  // running through the built-in local Whisper engine (see backend services/stt_service.py), so
  // unlike TTS/LLM there's no "nothing set up" warning callout here.
  const sttKeys = (keysQuery.data ?? []).filter((key) => {
    if (key.keyType !== "stt") return false;
    if (key.modelId) return true;
    return Boolean(findProvider(specs, key.provider)?.sttModelFixed);
  });
  const keysLoaded = keysQuery.isSuccess && providersQuery.isSuccess;
  const hasNoModels = keysLoaded && llmKeys.length === 0;
  const hasNoTtsKeys = keysLoaded && ttsKeys.length === 0;

  return (
    <>
      <div className={styles.field}>
        <label className={styles.label} htmlFor="llm-model">
          {t("apiDashboard.table.model")}
        </label>
        {hasNoModels ? (
          <Callout variant="warning">
            {t("configurator.step2.noLlmPrefix")} <Link to="/dashboard/api">{t("apiDashboard.title")}</Link>
            {t("configurator.step2.noLlmSuffix")}
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
              <option value={NO_MODEL_SELECTED}>{t("apiKeyForm.pleaseChoose")}</option>
              {llmKeys.map((key) => (
                <option key={key.id} value={key.id}>
                  {keyDisplayName(key, specs)} · {modelLabel(key, specs)}
                </option>
              ))}
            </select>
            <p className={styles.hint}>{t("configurator.step2.modelHint")}</p>
          </>
        )}
      </div>

      <div className={styles.field}>
        <label className={styles.label} htmlFor="temperature">
          {t("configurator.step2.temperature")}
        </label>
        <div className={styles.sliderRow}>
          <input
            id="temperature"
            type="range"
            min={0}
            max={MAX_TEMPERATURE}
            step={0.1}
            value={draft.temperature}
            onChange={(e) => onChange({ temperature: Number(e.target.value) })}
          />
          <span className={styles.sliderValue}>{draft.temperature.toFixed(1)}</span>
        </div>
        <p className={styles.hint}>{t("configurator.step2.temperatureHint")}</p>
      </div>

      <div className={styles.field}>
        <label className={styles.label} htmlFor="top-p">
          {t("configurator.step2.topP")}
        </label>
        <div className={styles.sliderRow}>
          <input
            id="top-p"
            type="range"
            min={0}
            max={MAX_TOP_P}
            step={0.05}
            value={draft.topP}
            onChange={(e) => onChange({ topP: Number(e.target.value) })}
          />
          <span className={styles.sliderValue}>{draft.topP.toFixed(2)}</span>
        </div>
        <p className={styles.hint}>{t("configurator.step2.topPHint")}</p>
      </div>

      <div className={styles.field}>
        <label className={styles.label} htmlFor="spoken-language">
          {t("configurator.step2.language")}
        </label>
        <select
          id="spoken-language"
          className={styles.select}
          value={draft.spokenLanguage}
          onChange={(e) => onChange({ spokenLanguage: e.target.value as typeof draft.spokenLanguage })}
        >
          {SPOKEN_LANGUAGE_VALUES.map((value) => (
            <option key={value} value={value}>
              {t(`configurator.step2.spokenLanguageOptions.${value}`)}
            </option>
          ))}
        </select>
        <p className={styles.hint}>{t("configurator.step2.languageHint")}</p>
      </div>

      <label className={styles.toggleRow}>
        <input
          type="checkbox"
          checked={draft.ttsEnabled}
          onChange={(e) => onChange({ ttsEnabled: e.target.checked })}
        />
        <span className={styles.toggleCopy}>
          <strong>{t("configurator.step2.ttsTitle")}</strong>
          <span>{t("configurator.step2.ttsText")}</span>
        </span>
      </label>

      {draft.ttsEnabled && (
        <div className={styles.field}>
          <label className={styles.label} htmlFor="tts-key">
            {t("configurator.step2.ttsKey")}
          </label>
          {hasNoTtsKeys ? (
            <Callout variant="warning">
              {t("configurator.step2.noTtsPrefix")} <Link to="/dashboard/api">{t("apiDashboard.title")}</Link>
              {t("configurator.step2.noTtsSuffix")}
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
                <option value={NO_MODEL_SELECTED}>{t("apiKeyForm.pleaseChoose")}</option>
                {ttsKeys.map((key) => (
                  <option key={key.id} value={key.id}>
                    {keyDisplayName(key, specs)} · {modelLabel(key, specs)}
                  </option>
                ))}
              </select>
              <Input
                label={t("configurator.step2.voiceOptional")}
                placeholder={t("configurator.step2.voicePlaceholder")}
                value={draft.ttsVoice}
                onChange={(e) => onChange({ ttsVoice: e.target.value })}
              />
              <p className={styles.hint}>{t("configurator.step2.voiceHint")}</p>
            </>
          )}

          <label className={styles.toggleRow}>
            <input
              type="checkbox"
              checked={draft.streamingEnabled}
              onChange={(e) => onChange({ streamingEnabled: e.target.checked })}
            />
            <span className={styles.toggleCopy}>
              <strong>{t("configurator.step2.streamingTitle")}</strong>
              <span>{t("configurator.step2.streamingText")}</span>
            </span>
          </label>
        </div>
      )}

      <label className={styles.toggleRow}>
        <input
          type="checkbox"
          checked={draft.sttEnabled}
          onChange={(e) => onChange({ sttEnabled: e.target.checked })}
        />
        <span className={styles.toggleCopy}>
          <strong>{t("configurator.step2.sttTitle")}</strong>
          <span>{t("configurator.step2.sttText")}</span>
        </span>
      </label>

      {draft.sttEnabled && (
        <div className={styles.field}>
          <label className={styles.label} htmlFor="stt-key">
            {t("configurator.step2.sttKey")}
          </label>
          <select
            id="stt-key"
            className={styles.select}
            value={draft.sttApiKeyId ?? NO_MODEL_SELECTED}
            onChange={(e) => onChange({ sttApiKeyId: e.target.value || null })}
            disabled={!keysLoaded}
          >
            <option value={NO_MODEL_SELECTED}>{t("configurator.step2.sttKeyDefault")}</option>
            {sttKeys.map((key) => (
              <option key={key.id} value={key.id}>
                {keyDisplayName(key, specs)} · {modelLabel(key, specs)}
              </option>
            ))}
          </select>
          <p className={styles.hint}>{t("configurator.step2.sttKeyHint")}</p>
        </div>
      )}
    </>
  );
}
