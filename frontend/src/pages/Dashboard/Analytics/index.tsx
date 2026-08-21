import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Download, ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/Button";
import { Tile } from "@/components/Tile";
import { Callout } from "@/components/Callout";
import { BarChart } from "@/components/Chart";
import { analyticsApi } from "@/api/analytics";
import { projectsApi } from "@/api/projects";
import { formatCompactNumber, formatDuration, formatEuro, numberLocale } from "@/lib/format";
import type { AnalyticsFilters, Granularity } from "@/types/analytics";
import styles from "./Analytics.module.css";

const PERIOD_OPTIONS = [
  { value: 7, days: 7 },
  { value: 30, days: 30 },
  { value: 90, days: 90 },
];

const PAGE_SIZE = 4;

const DEFAULT_FILTERS: AnalyticsFilters = { projectId: null, periodDays: 30, model: null };

// Screen 1f — Tab Auswertung
export function AnalyticsPage() {
  const { t } = useTranslation();
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
        <h2>{t("nav.analytics")}</h2>
        <Button onClick={handleExport}>
          <Download size={16} /> {t("analytics.csvExport")}
        </Button>
      </div>

      {exportError && <Callout variant="danger">{t("analytics.exportError")}</Callout>}

      <div className={styles.filterRow}>
        <select
          className={styles.select}
          value={draftFilters.projectId ?? ""}
          onChange={(e) => setDraftFilters((f) => ({ ...f, projectId: e.target.value || null }))}
        >
          <option value="">{t("analytics.filters.projectAll")}</option>
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
              {t("analytics.filters.period", { days: option.days })}
            </option>
          ))}
        </select>
        <select
          className={styles.select}
          value={draftFilters.model ?? ""}
          onChange={(e) => setDraftFilters((f) => ({ ...f, model: e.target.value || null }))}
        >
          <option value="">{t("analytics.filters.modelAll")}</option>
          {usedModels.map((model) => (
            <option key={model} value={model!}>
              {model}
            </option>
          ))}
        </select>
        <Button variant="accent" size="sm" onClick={applyFilters}>
          {t("analytics.filters.apply")}
        </Button>
      </div>

      <div className={styles.statGrid}>
        <Tile
          label={t("analytics.stats.sessions")}
          value={stats ? formatCompactNumber(stats.sessions) : "–"}
          delta={stats && { value: stats.sessionsDeltaPct, goodDirection: "up" }}
        />
        <Tile
          label={t("analytics.stats.messages")}
          value={stats ? formatCompactNumber(stats.messages) : "–"}
          delta={stats && { value: stats.messagesDeltaPct, goodDirection: "up" }}
        />
        <Tile
          label={t("analytics.stats.avgDuration")}
          value={stats ? formatDuration(stats.avgDurationSeconds) : "–"}
          delta={stats && { value: stats.avgDurationDeltaPct, goodDirection: "up" }}
        />
        <Tile
          label={t("analytics.stats.tokenCost")}
          value={stats ? formatEuro(stats.tokenCostEur) : "–"}
          delta={stats && { value: stats.tokenCostDeltaPct, goodDirection: "down" }}
        />
      </div>

      <div className={styles.card}>
        <div className={styles.cardHeader}>
          <h3>{t("analytics.sessionsOverTime")}</h3>
          <div className={styles.granularityToggle}>
            {(["day", "week", "month"] as Granularity[]).map((g) => (
              <button
                key={g}
                className={`${styles.granularityButton} ${granularity === g ? styles.granularityActive : ""}`}
                onClick={() => setGranularity(g)}
              >
                {t(`analytics.granularity.${g}`)}
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
              <th>{t("analytics.table.project")}</th>
              <th>{t("analytics.table.started")}</th>
              <th>{t("analytics.table.messagesAbbr")}</th>
              <th>{t("analytics.table.duration")}</th>
              <th>{t("analytics.table.lastQuestion")}</th>
            </tr>
          </thead>
          <tbody>
            {sessions.length === 0 ? (
              <tr className={styles.emptyRow}>
                <td colSpan={5}>{t("analytics.table.empty")}</td>
              </tr>
            ) : (
              sessions.map((session) => (
                <tr key={session.id}>
                  <td>{session.projectTitle}</td>
                  <td>{new Date(session.startedAt).toLocaleString(numberLocale())}</td>
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
            <p className={styles.emptyRow}>{t("analytics.table.empty")}</p>
          ) : (
            sessions.map((session) => (
              <div key={session.id} className={styles.sessionCard}>
                <div className={styles.sessionCardTop}>
                  <span>{session.projectTitle}</span>
                  <span>{formatDuration(session.durationSeconds)}</span>
                </div>
                <div className={styles.sessionCardMeta}>
                  <span>{new Date(session.startedAt).toLocaleDateString(numberLocale())}</span>
                  <span>{t("analytics.table.messagesCount", { count: session.messageCount })}</span>
                </div>
              </div>
            ))
          )}
        </div>

        <div className={styles.pagination}>
          <span>
            {totalSessions === 0
              ? t("analytics.pagination.zero")
              : t("analytics.pagination.range", {
                  from: (page - 1) * PAGE_SIZE + 1,
                  to: (page - 1) * PAGE_SIZE + sessions.length,
                  total: formatCompactNumber(totalSessions),
                })}
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
