import { useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/Button";
import { Callout } from "@/components/Callout";
import { LabelWithInfo } from "@/components/InfoTip";
import { Input } from "@/components/Input";
import { curatedModels, findProvider } from "@/lib/providers";
import { ALL_KEY_TYPES, KEY_TYPE_LABELS, type ApiKey, type ApiKeyInput, type ApiKeyType, type ProviderSpec } from "@/types/apiKey";
import styles from "./ApiDashboard.module.css";

// Sentinel in the model dropdown: "none of the curated options" — shows the free-text field and is
// never sent to the backend.
const FREE_TEXT_MODEL = "__free_text_model__";
// While nothing is chosen, the dropdown shows a placeholder instead of a seeming selection.
const NO_MODEL = "";

interface ApiKeyFormProps {
  specs: ProviderSpec[];
  // Set = editing an existing entry, otherwise creating a new one.
  editing?: ApiKey;
  pending: boolean;
  errorMessage?: string;
  onSubmit: (input: ApiKeyInput) => void;
  onCancel?: () => void;
}

export function ApiKeyForm({ specs, editing, pending, errorMessage, onSubmit, onCancel }: ApiKeyFormProps) {
  const { t } = useTranslation();
  const [provider, setProvider] = useState(editing?.provider ?? specs[0].value);
  const [apiBase, setApiBase] = useState(editing?.apiBase ?? specs[0].defaultApiBase ?? "");
  const [label, setLabel] = useState(editing?.label ?? "");
  const [keyType, setKeyType] = useState<ApiKeyType>(editing?.keyType ?? "llm");
  const [modelId, setModelId] = useState(editing?.modelId ?? "");
  const [arcanaId, setArcanaId] = useState(editing?.arcanaId ?? "");
  const [apiKeyValue, setApiKeyValue] = useState("");
  const [freeTextModel, setFreeTextModel] = useState(false);

  // Only providers that actually support the chosen type are offered below — choosing the type
  // first and narrowing the provider list from it (instead of the other way round) means the
  // dropdown never shows an endpoint that couldn't be used for what was just picked.
  const eligibleSpecs = specs.filter((option) => option.supportedTypes.includes(keyType));
  const spec = findProvider(eligibleSpecs, provider) ?? eligibleSpecs[0] ?? specs[0];
  const availableKeyTypes = ALL_KEY_TYPES.filter((type) => specs.some((option) => option.supportedTypes.includes(type)));
  // Embedding keys pick from the provider's embedding models, every other type from its chat models.
  const models = curatedModels(spec, keyType);
  // A stored model that isn't in the curated list was entered as free text (or the provider keeps
  // no list at all) — then the dropdown shows the free-text entry as active, with the input field
  // below it.
  const isCuratedModel = models.some((model) => model.value === modelId);
  const showFreeTextModel = freeTextModel || (Boolean(modelId) && !isCuratedModel);
  const modelSelectValue = showFreeTextModel ? FREE_TEXT_MODEL : modelId || NO_MODEL;
  // TTS providers with a hard-wired speech output model (spec.ttsModelFixed, e.g. OpenAI/Gemini)
  // need no model choice — features/ai/tts always uses the same model for them anyway, never the
  // model_id stored here.
  // (Same for an STT provider with spec.sttModelFixed, currently GWDG SAIA.)
  const showModelField = !((keyType === "tts" && spec.ttsModelFixed) || (keyType === "stt" && spec.sttModelFixed));

  function handleProviderChange(nextProvider: string) {
    const nextSpec = findProvider(specs, nextProvider);
    if (!nextSpec) return;
    setProvider(nextProvider);
    // Prefill without overwriting the user's own input: only if the field is empty or still
    // contains exactly the default of the previously chosen provider.
    if (!apiBase.trim() || apiBase === spec.defaultApiBase) {
      setApiBase(nextSpec.defaultApiBase ?? "");
    }
    // Models are provider-specific — a selection from the old provider makes no sense here.
    if (!curatedModels(nextSpec, keyType).some((model) => model.value === modelId)) {
      setModelId("");
      setFreeTextModel(false);
    }
  }

  // If switching the type just made the current provider ineligible, jump to the first provider
  // that still supports it — the inverse of the old provider→type fallback. Depends on
  // specs/keyType/provider (not the freshly-filtered eligibleSpecs array) so this only re-runs
  // when one of those actually changes, not on every render.
  useEffect(() => {
    if (!eligibleSpecs.some((option) => option.value === provider)) {
      const fallback = eligibleSpecs[0];
      if (fallback) handleProviderChange(fallback.value);
    }
  }, [keyType, specs, provider]);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    onSubmit({
      provider,
      keyType,
      label: label.trim() || null,
      apiKey: apiKeyValue,
      apiBase: apiBase.trim() || null,
      modelId: showModelField ? modelId.trim() || null : null,
      arcanaId: spec.requiresArcanaId ? arcanaId.trim() || null : null,
    });
  }

  return (
    <form className={styles.customFormFields} onSubmit={handleSubmit}>
      {errorMessage && <Callout variant="danger">{errorMessage}</Callout>}

      <div className={styles.field}>
        <LabelWithInfo
          label={t("apiDashboard.table.type")}
          htmlFor="key-type-select"
          className={styles.label}
          info={t("apiKeyForm.keyTypeHint")}
        />
        <select
          id="key-type-select"
          className={styles.select}
          value={keyType}
          onChange={(e) => setKeyType(e.target.value as ApiKeyType)}
        >
          {availableKeyTypes.map((type) => (
            <option key={type} value={type}>
              {KEY_TYPE_LABELS[type]}
            </option>
          ))}
        </select>
      </div>

      <div className={styles.field}>
        <label className={styles.label} htmlFor="provider-select">
          {t("apiKeyForm.provider")}
        </label>
        <select
          id="provider-select"
          className={styles.select}
          value={provider}
          onChange={(e) => handleProviderChange(e.target.value)}
        >
          {eligibleSpecs.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        {spec.hint && <p className={styles.hint}>{spec.hint}</p>}
        {keyType === "tts" && spec.ttsModelFixed && (
          <p className={styles.hint}>{t("apiKeyForm.ttsModelFixedHint", { provider: spec.label })}</p>
        )}
        {keyType === "stt" && spec.sttModelFixed && (
          <p className={styles.hint}>{t("apiKeyForm.sttModelFixedHint", { provider: spec.label })}</p>
        )}
        {keyType === "embedding" && <p className={styles.hint}>{t("apiKeyForm.embeddingHint")}</p>}
      </div>

      <Input
        label={spec.apiBaseRequired ? t("apiKeyForm.apiBase") : t("apiKeyForm.apiBaseOptional")}
        type="url"
        placeholder={spec.defaultApiBase ?? "https://api.example.com/v1"}
        value={apiBase}
        onChange={(e) => setApiBase(e.target.value)}
        required={spec.apiBaseRequired}
      />

      <Input
        label={t("apiKeyForm.nameOptional")}
        placeholder={spec.label}
        value={label}
        onChange={(e) => setLabel(e.target.value)}
      />

      {showModelField && (
        <div className={styles.field}>
          <LabelWithInfo
            label={t("apiDashboard.table.model")}
            htmlFor="model-select"
            className={styles.label}
            info={t("apiKeyForm.modelHint")}
          />
          <select
            id="model-select"
            className={styles.select}
            value={modelSelectValue}
            onChange={(e) => {
              const value = e.target.value;
              // The free-text entry clears the selection and shows the input field instead.
              setModelId(value === FREE_TEXT_MODEL || value === NO_MODEL ? "" : value);
              setFreeTextModel(value === FREE_TEXT_MODEL);
            }}
            required
          >
            <option value={NO_MODEL}>{t("apiKeyForm.pleaseChoose")}</option>
            {models.map((model) => (
              <option key={model.value} value={model.value}>
                {model.label}
              </option>
            ))}
            <option value={FREE_TEXT_MODEL}>{t("apiKeyForm.customModel")}</option>
          </select>
          {showFreeTextModel && (
            <Input
              label={t("apiKeyForm.modelId")}
              placeholder={t("apiKeyForm.modelIdPlaceholder")}
              value={modelId}
              onChange={(e) => setModelId(e.target.value)}
              required
            />
          )}
        </div>
      )}

      {spec.requiresArcanaId && (
        <Input
          label={t("apiKeyForm.arcanaId")}
          placeholder={t("apiKeyForm.arcanaIdPlaceholder")}
          value={arcanaId}
          onChange={(e) => setArcanaId(e.target.value)}
          required
        />
      )}

      <Input
        label={editing ? t("apiKeyForm.apiKeyEditing") : spec.keyRequired ? t("apiKeyForm.apiKey") : t("apiKeyForm.apiKeyOptional")}
        type="password"
        placeholder={spec.keyPlaceholder}
        value={apiKeyValue}
        onChange={(e) => setApiKeyValue(e.target.value)}
        autoComplete="off"
        required={spec.keyRequired && !editing}
      />

      <div className={styles.keyCardActions}>
        <Button type="submit" variant="accent" disabled={pending}>
          {t("common.save")}
        </Button>
        {onCancel && (
          <Button type="button" onClick={onCancel}>
            {t("common.cancel")}
          </Button>
        )}
      </div>
    </form>
  );
}
