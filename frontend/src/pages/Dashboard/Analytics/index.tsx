import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download, ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/Button";
import { Tile } from "@/components/Tile";
import { Callout } from "@/components/Callout";
import { BarChart } from "@/components/Chart";
import { analyticsApi } from "@/api/analytics";
import { projectsApi } from "@/api/projects";
import { formatCompactNumber, formatDuration, formatEuro } from "@/lib/format";
import type { AnalyticsFilters, Granularity } from "@/types/analytics";
import styles from "./Analytics.module.css";

const PERIOD_OPTIONS = [
  { value: 7, label: "7 Tage" },
  { value: 30, label: "30 Tage" },
  { value: 90, label: "90 Tage" },
];

const PAGE_SIZE = 4;

const DEFAULT_FILTERS: AnalyticsFilters = { projectId: null, periodDays: 30, model: null };

// Screen 1f — Tab Auswertung
export function AnalyticsPage() {
  // "Filter anwenden" im Wireframe impliziert zwei Zustände: was gerade in den Dropdowns steht
  // (draft) und was tatsächlich die Abfragen bestimmt (applied) — erst der Button übernimmt.
  const [draftFilters, setDraftFilters] = useState(DEFAULT_FILTERS);
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [granularity, setGranularity] = useState<Granularity>("week");
  const [page, setPage] = useState(1);
  const [exportError, setExportError] = useState(false);

  const projectsQuery = useQuery({ queryKey: ["projects"], queryFn: projectsApi.list });
  const statsQuery = useQuery({ queryKey: ["analytics", "stats", filters], queryFn: () => analyticsApi.stats(filters) });
  const timeseriesQuery = useQuery({
    queryKey: ["analytics", "timeseries", filters, granularity],
    queryFn: () => analyticsApi.timeseries(filters, granularity),
  });
  const sessionsQuery = useQuery({
    queryKey: ["analytics", "sessions", filters, page],
    queryFn: () => analyticsApi.sessions(filters, page),
  });

  const stats = statsQuery.data;
  // Nur Modelle anbieten, die tatsächlich in Projekten stehen — der Filter vergleicht serverseitig
  // exakt gegen Project.llm_model, eine feste Liste würde also auch Optionen ohne jeden Treffer
  // enthalten.
  const usedModels = [...new Set((projectsQuery.data ?? []).map((p) => p.llmModel).filter(Boolean))].sort();
  const sessions = sessionsQuery.data?.items ?? [];
  const totalSessions = sessionsQuery.data?.total ?? 0;
  const timeseries = timeseriesQuery.data ?? [];

  function applyFilters() {
    setFilters(draftFilters);
    setPage(1);
  }

  async function handleExport() {
    setExportError(false);
    try {
      await analyticsApi.exportCsv(filters);
    } catch {
      setExportError(true);
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.topbar}>
        <h2>Auswertung</h2>
        <Button onClick={handleExport}>
          <Download size={16} /> CSV-Export
        </Button>
      </div>

      {exportError && <Callout variant="danger">Export fehlgeschlagen. Bitte erneut versuchen.</Callout>}

      <div className={styles.filterRow}>
        <select
          className={styles.select}
          value={draftFilters.projectId ?? ""}
          onChange={(e) => setDraftFilters((f) => ({ ...f, projectId: e.target.value || null }))}
        >
          <option value="">Projekt: Alle</option>
          {(projectsQuery.data ?? []).map((project) => (
            <option key={project.id} value={project.id}>
              {project.title}
            </option>
          ))}
        </select>
        <select
          className={styles.select}
          value={draftFilters.periodDays}
          onChange={(e) => setDraftFilters((f) => ({ ...f, periodDays: Number(e.target.value) }))}
        >
          {PERIOD_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              Zeitraum: {option.label}
            </option>
          ))}
        </select>
        <select
          className={styles.select}
          value={draftFilters.model ?? ""}
          onChange={(e) => setDraftFilters((f) => ({ ...f, model: e.target.value || null }))}
        >
          <option value="">Modell: Alle</option>
          {usedModels.map((model) => (
            <option key={model} value={model!}>
              {model}
            </option>
          ))}
        </select>
        <Button variant="accent" size="sm" onClick={applyFilters}>
          Filter anwenden
        </Button>
      </div>

      <div className={styles.statGrid}>
        <Tile
          label="Sessions"
          value={stats ? formatCompactNumber(stats.sessions) : "–"}
          delta={stats && { value: stats.sessionsDeltaPct, goodDirection: "up" }}
        />
        <Tile
          label="Nachrichten"
          value={stats ? formatCompactNumber(stats.messages) : "–"}
          delta={stats && { value: stats.messagesDeltaPct, goodDirection: "up" }}
        />
        <Tile
          label="Ø Dauer"
          value={stats ? formatDuration(stats.avgDurationSeconds) : "–"}
          delta={stats && { value: stats.avgDurationDeltaPct, goodDirection: "up" }}
        />
        <Tile
          label="Token-Kosten"
          value={stats ? formatEuro(stats.tokenCostEur) : "–"}
          delta={stats && { value: stats.tokenCostDeltaPct, goodDirection: "down" }}
        />
      </div>

      <div className={styles.card}>
        <div className={styles.cardHeader}>
          <h3>Sessions im Zeitverlauf</h3>
          <div className={styles.granularityToggle}>
            {(["day", "week", "month"] as Granularity[]).map((g) => (
              <button
                key={g}
                className={`${styles.granularityButton} ${granularity === g ? styles.granularityActive : ""}`}
                onClick={() => setGranularity(g)}
              >
                {g === "day" ? "Tag" : g === "week" ? "Woche" : "Monat"}
              </button>
            ))}
          </div>
        </div>
        <BarChart data={timeseries} isFetching={timeseriesQuery.isFetching} />
      </div>

      <div className={styles.card}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Projekt</th>
              <th>Gestartet</th>
              <th>Nachr.</th>
              <th>Dauer</th>
              <th>Letzte Frage</th>
            </tr>
          </thead>
          <tbody>
            {sessions.length === 0 ? (
              <tr className={styles.emptyRow}>
                <td colSpan={5}>Keine Sessions für diesen Filter.</td>
              </tr>
            ) : (
              sessions.map((session) => (
                <tr key={session.id}>
                  <td>{session.projectTitle}</td>
                  <td>{new Date(session.startedAt).toLocaleString("de-DE")}</td>
                  <td>{session.messageCount}</td>
                  <td>{formatDuration(session.durationSeconds)}</td>
                  <td>{session.lastQuestion ?? "–"}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>

        <div className={styles.sessionCards}>
          {sessions.length === 0 ? (
            <p className={styles.emptyRow}>Keine Sessions für diesen Filter.</p>
          ) : (
            sessions.map((session) => (
              <div key={session.id} className={styles.sessionCard}>
                <div className={styles.sessionCardTop}>
                  <span>{session.projectTitle}</span>
                  <span>{formatDuration(session.durationSeconds)}</span>
                </div>
                <div className={styles.sessionCardMeta}>
                  <span>{new Date(session.startedAt).toLocaleDateString("de-DE")}</span>
                  <span>{session.messageCount} Nachr.</span>
                </div>
              </div>
            ))
          )}
        </div>

        <div className={styles.pagination}>
          <span>
            {totalSessions === 0
              ? "0 von 0"
              : `${(page - 1) * PAGE_SIZE + 1}–${(page - 1) * PAGE_SIZE + sessions.length} von ${formatCompactNumber(totalSessions)}`}
          </span>
          <div className={styles.pageButtons}>
            <Button size="sm" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}>
              <ChevronLeft size={14} />
            </Button>
            <Button
              size="sm"
              onClick={() => setPage((p) => p + 1)}
              disabled={page * PAGE_SIZE >= totalSessions}
            >
              <ChevronRight size={14} />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
