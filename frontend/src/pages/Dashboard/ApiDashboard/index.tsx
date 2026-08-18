import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Trash2 } from "lucide-react";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Callout } from "@/components/Callout";
import { apiKeysApi } from "@/api/apiKeys";
import { errorMessage } from "@/api/client";
import { keyDisplayName, modelLabel, providerLabel, useProviders } from "@/lib/providers";
import { KEY_TYPE_LABELS, type ApiKey, type ApiKeyInput, type ApiKeyStatus } from "@/types/apiKey";
import { ApiKeyForm } from "./ApiKeyForm";
import styles from "./ApiDashboard.module.css";

const STATUS_VARIANT: Record<ApiKeyStatus, "accent" | "default" | "danger"> = {
  active: "accent",
  unverified: "default",
  error: "danger",
};

const STATUS_LABEL: Record<ApiKeyStatus, string> = {
  active: "Aktiv",
  unverified: "Ungeprüft",
  error: "Fehler",
};

// Screen 1g — Tab API-Dashboard
export function ApiDashboardPage() {
  const queryClient = useQueryClient();
  const providersQuery = useProviders();
  const keysQuery = useQuery({ queryKey: ["api-keys"], queryFn: apiKeysApi.list });
  const specs = providersQuery.data ?? [];
  const keys = keysQuery.data ?? [];

  const [editingKey, setEditingKey] = useState<ApiKey | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  // Ergebnis des zuletzt gedrückten "Test"-Buttons, je Key — enthält bei Fehlschlag die Ursache.
  const [testResult, setTestResult] = useState<{ id: string; status: string; message: string | null } | null>(null);

  function closeForm() {
    setFormOpen(false);
    setEditingKey(null);
  }

  const saveMutation = useMutation({
    mutationFn: (input: ApiKeyInput) =>
      editingKey ? apiKeysApi.update(editingKey.id, input) : apiKeysApi.create(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
      // Ein Modellwechsel am Key ändert den gespeicherten Modellstring der Projekte.
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      closeForm();
    },
  });

  const testMutation = useMutation({
    mutationFn: (id: string) => apiKeysApi.test(id).then((result) => ({ id, ...result })),
    onSuccess: (result) => {
      setTestResult(result);
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
    },
  });

  const removeMutation = useMutation({
    mutationFn: (id: string) => apiKeysApi.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  function handleRemove(key: ApiKey) {
    // Absichtlich ein zweiter, expliziter Schritt (siehe Wireframe-Annotation zu 1g) —
    // "Entfernen" widerruft einen Key für alle Projekte, das braucht bewusste Reibung.
    const used =
      key.usedByProjects > 0
        ? `\n\n${key.usedByProjects} Projekt${key.usedByProjects === 1 ? "" : "e"} nutzt dieses Modell und verliert dadurch die Modellwahl.`
        : "";
    if (window.confirm(`Schlüssel "${keyDisplayName(key, specs)}" wirklich entfernen?${used}`)) {
      removeMutation.mutate(key.id);
    }
  }

  function openEdit(key: ApiKey) {
    saveMutation.reset();
    setEditingKey(key);
    setFormOpen(true);
  }

  function openCreate() {
    saveMutation.reset();
    setEditingKey(null);
    setFormOpen(true);
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h2>API-Schlüssel</h2>
        <p>Deine Keys werden verschlüsselt gespeichert und nie im Klartext angezeigt.</p>
      </div>

      <Callout variant="info">
        <span className={styles.calloutFull}>
          Sicherheitshinweis: Keys gelten für alle deine Projekte. Bei Verdacht auf Missbrauch sofort widerrufen und
          beim Anbieter neu erzeugen.
        </span>
        <span className={styles.calloutShort}>Keys werden verschlüsselt gespeichert.</span>
      </Callout>

      {testResult?.status === "error" && (
        <Callout variant="danger">
          Test fehlgeschlagen: {testResult.message ?? "Der Anbieter hat den Schlüssel abgelehnt."}
        </Callout>
      )}
      {testResult?.status === "active" && <Callout variant="success">Schlüssel erfolgreich getestet.</Callout>}

      <div className={styles.card}>
        {/* Sieben Spalten passen auf schmaleren Desktops nicht immer — scrollen statt überlaufen. */}
        <div className={styles.tableScroll}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Name</th>
              <th>Typ</th>
              <th>Modell</th>
              <th>Schlüssel</th>
              <th>Hinzugefügt</th>
              <th>Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {keys.map((key) => (
              <tr key={key.id}>
                <td>
                  {keyDisplayName(key, specs)}
                  <div className={styles.hint}>{providerLabel(specs, key.provider)}</div>
                </td>
                <td>
                  <Badge variant={key.keyType === "llm" ? "accent" : "default"}>{KEY_TYPE_LABELS[key.keyType]}</Badge>
                </td>
                <td>{modelLabel(key, specs) ?? "–"}</td>
                <td className="mono">
                  {key.maskedKey || "–"}
                  {key.apiBase && <div className={styles.hint}>{key.apiBase}</div>}
                </td>
                <td>{new Date(key.addedAt).toLocaleDateString("de-DE")}</td>
                <td>
                  <Badge variant={STATUS_VARIANT[key.status]}>{STATUS_LABEL[key.status]}</Badge>
                </td>
                <td>
                  <div className={styles.actions}>
                    <Button size="sm" onClick={() => testMutation.mutate(key.id)} disabled={testMutation.isPending}>
                      Test
                    </Button>
                    <Button size="sm" onClick={() => openEdit(key)} aria-label="Bearbeiten" title="Bearbeiten">
                      <Pencil size={14} />
                    </Button>
                    <Button
                      size="sm"
                      onClick={() => handleRemove(key)}
                      disabled={removeMutation.isPending}
                      aria-label="Entfernen"
                      title="Entfernen"
                    >
                      <Trash2 size={14} />
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>

        <div className={styles.keyCards}>
          {keys.map((key) => (
            <div key={key.id} className={styles.keyCard}>
              <div className={styles.keyCardTop}>
                <strong>{keyDisplayName(key, specs)}</strong>
                <div className={styles.badgeRow}>
                  <Badge variant={key.keyType === "llm" ? "accent" : "default"}>{KEY_TYPE_LABELS[key.keyType]}</Badge>
                  <Badge variant={STATUS_VARIANT[key.status]}>{STATUS_LABEL[key.status]}</Badge>
                </div>
              </div>
              <span className={styles.hint}>
                {providerLabel(specs, key.provider)}
                {modelLabel(key, specs) && ` · ${modelLabel(key, specs)}`}
              </span>
              <span className="mono">{key.maskedKey || "–"}</span>
              {key.apiBase && <span className={styles.hint}>{key.apiBase}</span>}
              <div className={styles.keyCardActions}>
                <Button size="sm" onClick={() => testMutation.mutate(key.id)} disabled={testMutation.isPending}>
                  Testen
                </Button>
                <Button size="sm" onClick={() => openEdit(key)}>
                  Bearbeiten
                </Button>
                <Button size="sm" onClick={() => handleRemove(key)} disabled={removeMutation.isPending}>
                  Entfernen
                </Button>
              </div>
            </div>
          ))}
        </div>

        {keys.length === 0 && !keysQuery.isLoading && (
          <p className={styles.empty}>Noch keine API-Schlüssel hinterlegt.</p>
        )}
      </div>

      <div className={styles.card}>
        <h3>{editingKey ? "Schlüssel bearbeiten" : "Neuen Schlüssel hinzufügen"}</h3>
        {providersQuery.isError && <Callout variant="danger">Anbieterliste konnte nicht geladen werden.</Callout>}
        {specs.length > 0 &&
          (formOpen ? (
            <ApiKeyForm
              // Beim Wechsel zwischen Anlegen und Bearbeiten sollen die Felder neu aus dem
              // jeweiligen Datensatz initialisiert werden, nicht die alte Eingabe behalten.
              key={editingKey?.id ?? "new"}
              specs={specs}
              editing={editingKey ?? undefined}
              pending={saveMutation.isPending}
              errorMessage={
                saveMutation.isError
                  ? errorMessage(saveMutation.error, "Speichern fehlgeschlagen. Bitte Angaben prüfen.")
                  : undefined
              }
              onSubmit={(input) => saveMutation.mutate(input)}
              onCancel={closeForm}
            />
          ) : (
            <Button onClick={openCreate}>+ Schlüssel hinzufügen</Button>
          ))}
      </div>
    </div>
  );
}
