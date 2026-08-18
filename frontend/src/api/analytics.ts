import { apiClient } from "./client";
import type { AnalyticsFilters, AnalyticsStats, Granularity, SessionsPage, TimeseriesPoint } from "@/types/analytics";

function filterParams(filters: AnalyticsFilters): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.projectId) params.set("project_id", filters.projectId);
  params.set("period_days", String(filters.periodDays));
  if (filters.model) params.set("model", filters.model);
  return params;
}

export const analyticsApi = {
  stats: (filters: AnalyticsFilters) => apiClient.get<AnalyticsStats>(`/analytics/stats?${filterParams(filters)}`),

  // { items, total } statt einer nackten Liste, damit "1–4 von 1.284" echte Pagination ist.
  sessions: (filters: AnalyticsFilters, page: number) => {
    const params = filterParams(filters);
    params.set("page", String(page));
    return apiClient.get<SessionsPage>(`/analytics/sessions?${params}`);
  },

  timeseries: (filters: AnalyticsFilters, granularity: Granularity) => {
    const params = filterParams(filters);
    params.set("granularity", granularity);
    return apiClient.get<TimeseriesPoint[]>(`/analytics/timeseries?${params}`);
  },

  // Lädt die CSV direkt als Datei herunter, statt sie wie die übrigen Endpunkte als JSON zu parsen.
  exportCsv: async (filters: AnalyticsFilters) => {
    const res = await fetch(`/api/analytics/export.csv?${filterParams(filters)}`, { credentials: "include" });
    if (!res.ok) throw new Error("Export fehlgeschlagen");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "sessions.csv";
    link.click();
    URL.revokeObjectURL(url);
  },
};
