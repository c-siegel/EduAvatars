import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Callout } from "@/components/Callout";
import { Input } from "@/components/Input";
import { apiKeysApi } from "@/api/apiKeys";
import { voiceClipsApi } from "@/api/voiceClips";
import {
  findProvider,
  keyDisplayName,
  modelLabel,
  useBrowserSttStatus,
  useLocalTtsStatus,
  useProviders,
  useServerSttStatus,
} from "@/lib/providers";
import { SPOKEN_LANGUAGE_VALUES } from "@/lib/speechOptions";
import type { SttServerEngine } from "@/types/project";
import type { StepProps } from "../types";
import styles from "./shared.module.css";

// Placeholder while no key has been chosen yet — a <select> always needs a controlled string
// value, but draft.llmApiKeyId is null until the teacher picks one.
const NO_MODEL_SELECTED = "";

// The STT dropdown mixes two kinds of choices in one <select>: a server engine (stored in
// draft.sttServerEngine) or an STT key (draft.sttApiKeyId). Engine options get this prefix so
// their values can never collide with a key id.
const STT_ENGINE_PREFIX = "engine:";
const STT_SERVER_ENGINES: SttServerEngine[] = ["whisper", "parakeet"];

// Upper bounds of the two sampling parameters — the backend checks the same values again
// (MAX_TEMPERATURE/MAX_TOP_P in backend/app/features/projects/schemas.py), so a value set via
// the API can't get around the slider.
const MAX_TEMPERATURE = 2;
const MAX_TOP_P = 1;

// Step 2 — technical: model, sampling (temperature/top P), language, TTS and STT.
export function Step2Technical({ draft, onChange }: StepProps) {
  const { t } = useTranslation();
  // Only keys of type LLM that are actually configured are offered (screen 1g). Previously the
  // dropdown listed a fixed model list, which suggested availability that only existed once a
  // matching key had been added — the error then only showed up in the chat.
  const providersQuery = useProviders();
  const keysQuery = useQuery({ queryKey: ["api-keys"], queryFn: apiKeysApi.list });
  const localTtsStatusQuery = useLocalTtsStatus();
  const localTtsAvailable = localTtsStatusQuery.data?.available ?? false;
  // The teacher's own voice clips (Dashboard → Voices) — only offered when local TTS speaks, since
  // a cloud TTS provider uses its own voices.
  const voiceClipsQuery = useQuery({
    queryKey: ["voice-clips"],
    queryFn: voiceClipsApi.list,
    enabled: localTtsAvailable,
  });
  const voiceClips = voiceClipsQuery.data ?? [];
  const usesLocalTts = localTtsAvailable && draft.ttsApiKeyId === null;
  const browserSttStatusQuery = useBrowserSttStatus();
  const browserSttAvailable = browserSttStatusQuery.data?.available ?? false;
  const specs = providersQuery.data ?? [];
  const llmKeys = (keysQuery.data ?? []).filter((key) => key.keyType === "llm" && key.modelId);
  // Like the LLM model, TTS picks a configured key directly (screen 1g), no fixed provider list
  // anymore — this automatically covers every provider the registry supports for TTS (OpenAI,
  // Gemini, Cartesia, a custom OpenAI-compatible endpoint).
  // Providers with a hard-wired TTS model (ttsModelFixed) deliberately store no modelId (see
  // ApiKeyForm.tsx) — they still need to count as selectable here.
  const ttsKeys = (keysQuery.data ?? []).filter((key) => {
    if (key.keyType !== "tts") return false;
    if (key.modelId) return true;
    return Boolean(findProvider(specs, key.provider)?.ttsModelFixed);
  });
  // STT (currently only GWDG SAIA) is optional — with no key selected, transcription keeps
  // running through a built-in local engine (Whisper or Parakeet, see backend features/ai/stt), so
  // unlike LLM there's no "nothing set up" warning callout here. TTS below follows the same rule
  // once local TTS is available for this deployment (localTtsAvailable).
  const sttKeys = (keysQuery.data ?? []).filter((key) => {
    if (key.keyType !== "stt") return false;
    if (key.modelId) return true;
    return Boolean(findProvider(specs, key.provider)?.sttModelFixed);
  });
  const serverSttStatusQuery = useServerSttStatus();
  const defaultSttEngine = serverSttStatusQuery.data?.defaultEngine ?? "whisper";
  const parakeetAvailable = serverSttStatusQuery.data?.parakeetAvailable ?? false;
  const sttSelectValue = draft.sttApiKeyId
    ? draft.sttApiKeyId
    : draft.sttServerEngine
      ? STT_ENGINE_PREFIX + draft.sttServerEngine
      : NO_MODEL_SELECTED;
  function handleSttChoice(value: string) {
    if (value.startsWith(STT_ENGINE_PREFIX)) {
      onChange({ sttApiKeyId: null, sttServerEngine: value.slice(STT_ENGINE_PREFIX.length) as SttServerEngine });
    } else {
      // A key, or the deployment default — either way no engine of the project's own.
      onChange({ sttApiKeyId: value || null, sttServerEngine: null });
    }
  }
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
          {hasNoTtsKeys && !localTtsAvailable ? (
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
                <option value={NO_MODEL_SELECTED}>
                  {localTtsAvailable ? t("configurator.step2.ttsKeyDefault") : t("apiKeyForm.pleaseChoose")}
                </option>
                {ttsKeys.map((key) => (
                  <option key={key.id} value={key.id}>
                    {keyDisplayName(key, specs)} · {modelLabel(key, specs)}
                  </option>
                ))}
              </select>
              {/* Shown whenever leaving this project's key unset falls back to local TTS — not just
                  when the account has no TTS keys at all (this account may have keys for OTHER
                  projects and still leave this one on the local fallback). */}
              {localTtsAvailable && <p className={styles.hint}>{t("configurator.step2.ttsKeyHint")}</p>}
              {usesLocalTts ? (
                <>
                  <label className={styles.label} htmlFor="tts-voice-clip">
                    {t("configurator.step2.voiceClip")}
                  </label>
                  <select
                    id="tts-voice-clip"
                    className={styles.select}
                    value={draft.ttsVoiceClipId ?? ""}
                    onChange={(e) => onChange({ ttsVoiceClipId: e.target.value || null })}
                  >
                    <option value="">{t("configurator.step2.voiceClipDefault")}</option>
                    {voiceClips.map((clip) => (
                      <option key={clip.id} value={clip.id}>
                        {clip.name}
                      </option>
                    ))}
                  </select>
                  <p className={styles.hint}>
                    {t("configurator.step2.voiceClipHint")}{" "}
                    <Link to="/dashboard/voices">{t("nav.voices")}</Link>
                  </p>
                </>
              ) : (
                <>
                  <Input
                    label={t("configurator.step2.voiceOptional")}
                    placeholder={t("configurator.step2.voicePlaceholder")}
                    value={draft.ttsVoice}
                    onChange={(e) => onChange({ ttsVoice: e.target.value })}
                  />
                  <p className={styles.hint}>{t("configurator.step2.voiceHint")}</p>
                </>
              )}
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
            value={sttSelectValue}
            onChange={(e) => handleSttChoice(e.target.value)}
            disabled={!keysLoaded}
          >
            <option value={NO_MODEL_SELECTED}>
              {t("configurator.step2.sttKeyDefault", {
                engine: t(`configurator.step2.sttServerEngines.${defaultSttEngine}`),
              })}
            </option>
            {STT_SERVER_ENGINES.map((engine) => (
              <option
                key={engine}
                value={STT_ENGINE_PREFIX + engine}
                // Parakeet only runs once its model files are on the server — still listed (greyed
                // out) so the option is discoverable, and kept selectable if already chosen.
                disabled={engine === "parakeet" && !parakeetAvailable && draft.sttServerEngine !== "parakeet"}
              >
                {t("configurator.step2.sttServerEngineOption", {
                  engine: t(`configurator.step2.sttServerEngines.${engine}`),
                })}
                {engine === "parakeet" && !parakeetAvailable ? ` ${t("configurator.step2.sttParakeetMissing")}` : ""}
              </option>
            ))}
            {sttKeys.map((key) => (
              <option key={key.id} value={key.id}>
                {keyDisplayName(key, specs)} · {modelLabel(key, specs)}
              </option>
            ))}
          </select>
          <p className={styles.hint}>{t("configurator.step2.sttKeyHint")}</p>

          {browserSttAvailable && (
            <label className={styles.toggleRow}>
              <input
                type="checkbox"
                checked={draft.sttBrowserEnabled}
                onChange={(e) => onChange({ sttBrowserEnabled: e.target.checked })}
              />
              <span className={styles.toggleCopy}>
                <strong>{t("configurator.step2.sttBrowserTitle")}</strong>
                <span>{t("configurator.step2.sttBrowserText")}</span>
              </span>
            </label>
          )}
        </div>
      )}
    </>
  );
}
