import { useEffect, useState, type FormEvent } from "react";
import { Button } from "@/components/Button";
import { Callout } from "@/components/Callout";
import { Input } from "@/components/Input";
import { findProvider } from "@/lib/providers";
import { KEY_TYPE_LABELS, type ApiKey, type ApiKeyInput, type ApiKeyType, type ProviderSpec } from "@/types/apiKey";
import styles from "./ApiDashboard.module.css";

// Sentinel im Modell-Dropdown: "keine der kuratierten Optionen" — blendet das Freitextfeld ein und
// wird nie ans Backend geschickt.
const FREE_TEXT_MODEL = "__free_text_model__";
// Solange nichts gewählt ist, steht ein Platzhalter im Dropdown statt einer scheinbaren Auswahl.
const NO_MODEL = "";

interface ApiKeyFormProps {
  specs: ProviderSpec[];
  // Gesetzt = Bearbeiten eines bestehenden Eintrags, sonst Anlegen.
  editing?: ApiKey;
  pending: boolean;
  errorMessage?: string;
  onSubmit: (input: ApiKeyInput) => void;
  onCancel?: () => void;
}

export function ApiKeyForm({ specs, editing, pending, errorMessage, onSubmit, onCancel }: ApiKeyFormProps) {
  const [provider, setProvider] = useState(editing?.provider ?? specs[0].value);
  const [apiBase, setApiBase] = useState(editing?.apiBase ?? specs[0].defaultApiBase ?? "");
  const [label, setLabel] = useState(editing?.label ?? "");
  const [keyType, setKeyType] = useState<ApiKeyType>(editing?.keyType ?? "llm");
  const [modelId, setModelId] = useState(editing?.modelId ?? "");
  const [arcanaId, setArcanaId] = useState(editing?.arcanaId ?? "");
  const [apiKeyValue, setApiKeyValue] = useState("");
  const [freeTextModel, setFreeTextModel] = useState(false);

  const spec = findProvider(specs, provider) ?? specs[0];
  // Ein hinterlegtes Modell, das nicht in der kuratierten Liste steht, wurde als Freitext
  // eingetragen (oder der Anbieter pflegt gar keine Liste) — dann zeigt das Dropdown den
  // Freitext-Eintrag als aktiv und das Eingabefeld darunter.
  const isCuratedModel = spec.models.some((model) => model.value === modelId);
  const showFreeTextModel = freeTextModel || (Boolean(modelId) && !isCuratedModel);
  const modelSelectValue = showFreeTextModel ? FREE_TEXT_MODEL : modelId || NO_MODEL;
  // TTS-Anbieter mit fest verdrahtetem Sprachausgabe-Modell (spec.ttsModelFixed, z. B.
  // OpenAI/Gemini) brauchen keine Modellwahl — tts_service.py nutzt dort ohnehin immer dasselbe
  // Modell, nie das hier hinterlegte model_id.
  const showModelField = !(keyType === "tts" && spec.ttsModelFixed);

  function handleProviderChange(nextProvider: string) {
    const nextSpec = findProvider(specs, nextProvider);
    if (!nextSpec) return;
    setProvider(nextProvider);
    // Vorbelegen, ohne eine eigene Eingabe zu überschreiben: nur wenn das Feld leer ist oder noch
    // exakt den Default des vorher gewählten Anbieters enthält.
    if (!apiBase.trim() || apiBase === spec.defaultApiBase) {
      setApiBase(nextSpec.defaultApiBase ?? "");
    }
    // Modelle sind anbieterspezifisch — eine Auswahl des alten Anbieters ergibt hier keinen Sinn.
    if (!nextSpec.models.some((model) => model.value === modelId)) {
      setModelId("");
      setFreeTextModel(false);
    }
  }

  // Unterstützt der neue Anbieter den gewählten Typ nicht (z.B. TTS bei Anthropic), auf den ersten
  // unterstützten zurückfallen.
  useEffect(() => {
    if (!spec.supportedTypes.includes(keyType)) setKeyType(spec.supportedTypes[0]);
  }, [spec, keyType]);

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
        <label className={styles.label} htmlFor="provider-select">
          Anbieter / Kommunikationsprotokoll
        </label>
        <select
          id="provider-select"
          className={styles.select}
          value={provider}
          onChange={(e) => handleProviderChange(e.target.value)}
        >
          {specs.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        {spec.hint && <p className={styles.hint}>{spec.hint}</p>}
      </div>

      <Input
        label={spec.apiBaseRequired ? "Endpunkt-Adresse (API-Base-URL)" : "Endpunkt-Adresse (API-Base-URL, optional)"}
        type="url"
        placeholder={spec.defaultApiBase ?? "https://api.example.com/v1"}
        value={apiBase}
        onChange={(e) => setApiBase(e.target.value)}
        required={spec.apiBaseRequired}
      />

      <Input
        label="Name (optional)"
        placeholder={spec.label}
        value={label}
        onChange={(e) => setLabel(e.target.value)}
      />

      <div className={styles.field}>
        <label className={styles.label} htmlFor="key-type-select">
          Typ
        </label>
        <select
          id="key-type-select"
          className={styles.select}
          value={keyType}
          onChange={(e) => setKeyType(e.target.value as ApiKeyType)}
        >
          {spec.supportedTypes.map((type) => (
            <option key={type} value={type}>
              {KEY_TYPE_LABELS[type]}
            </option>
          ))}
        </select>
        {keyType === "tts" && spec.ttsModelFixed && (
          <p className={styles.hint}>
            {spec.label} nutzt für die Sprachausgabe immer ein festes Modell — eine Modellwahl
            entfällt hier.
          </p>
        )}
      </div>

      {showModelField && (
        <div className={styles.field}>
          <label className={styles.label} htmlFor="model-select">
            Modell
          </label>
          <select
            id="model-select"
            className={styles.select}
            value={modelSelectValue}
            onChange={(e) => {
              const value = e.target.value;
              // Der Freitext-Eintrag löscht die Auswahl und blendet stattdessen das Eingabefeld ein.
              setModelId(value === FREE_TEXT_MODEL || value === NO_MODEL ? "" : value);
              setFreeTextModel(value === FREE_TEXT_MODEL);
            }}
            required
          >
            <option value={NO_MODEL}>Bitte wählen …</option>
            {spec.models.map((model) => (
              <option key={model.value} value={model.value}>
                {model.label}
              </option>
            ))}
            <option value={FREE_TEXT_MODEL}>Eigenes Modell (Freitext) …</option>
          </select>
          {showFreeTextModel && (
            <Input
              label="Modell-ID"
              placeholder='z. B. "llama-3.1-70b" oder "qwen2.5"'
              value={modelId}
              onChange={(e) => setModelId(e.target.value)}
              required
            />
          )}
          <p className={styles.hint}>
            Genau dieses Modell steht danach im Konfigurator zur Auswahl. Die Modell-ID wird
            unverändert an den Anbieter weitergereicht — für die korrekte Schreibweise ist die
            Lehrkraft selbst verantwortlich.
          </p>
        </div>
      )}

      {spec.requiresArcanaId && (
        <Input
          label="Arcana-ID"
          placeholder="z. B. nutzername/Projektname"
          value={arcanaId}
          onChange={(e) => setArcanaId(e.target.value)}
          required
        />
      )}

      <Input
        label={editing ? "API-Key (leer lassen = unverändert)" : spec.keyRequired ? "API-Key" : "API-Key (optional)"}
        type="password"
        placeholder={spec.keyPlaceholder}
        value={apiKeyValue}
        onChange={(e) => setApiKeyValue(e.target.value)}
        autoComplete="off"
        required={spec.keyRequired && !editing}
      />

      <div className={styles.keyCardActions}>
        <Button type="submit" variant="accent" disabled={pending}>
          Speichern
        </Button>
        {onCancel && (
          <Button type="button" onClick={onCancel}>
            Abbrechen
          </Button>
        )}
      </div>
    </form>
  );
}
