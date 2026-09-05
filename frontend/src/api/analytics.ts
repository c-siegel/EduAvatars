import { apiClient, filenameFromContentDisposition } from "./client";
import type {
  AnalyticsFilters,
  AnalyticsStats,
  ConversationIdsRequest,
  Granularity,
  SessionDetail,
  SessionsPage,
  TimeseriesPoint,
} from "@/types/analytics";

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

  // Alle zum Filter passenden Konversations-IDs, unabhängig von der Seite — für den "Wähle alle"-
  // Knopf, siehe pages/Dashboard/Analytics/index.tsx.
  sessionIds: (filters: AnalyticsFilters) => apiClient.get<string[]>(`/analytics/sessions/ids?${filterParams(filters)}`),

  // Full transcript for one session's "view" action (see pages/Dashboard/Analytics/index.tsx) —
  // separate from `sessions` above since the table's paginated list stays a lightweight summary.
  sessionDetail: (id: string) => apiClient.get<SessionDetail>(`/analytics/sessions/${id}`),

  timeseries: (filters: AnalyticsFilters, granularity: Granularity) => {
    const params = filterParams(filters);
    params.set("granularity", granularity);
    return apiClient.get<TimeseriesPoint[]>(`/analytics/timeseries?${params}`);
  },

  // Lädt eine .csv (eine ausgewählte Konversation) oder .zip (mehrere) direkt als Datei herunter,
  // statt sie wie die übrigen Endpunkte als JSON zu parsen.
  exportConversations: async (conversationIds: string[]) => {
    const body: ConversationIdsRequest = { conversationIds };
    const res = await fetch(`/api/analytics/export`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error("Export fehlgeschlagen");
    const filename = filenameFromContentDisposition(res.headers.get("Content-Disposition"), "eduavatars-gespraeche.zip");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  },

  // Permanently deletes the checked-off conversations — ids that don't belong to the current
  // user are silently skipped server-side (see app/api/analytics.py::delete_conversations_route).
  deleteConversations: (conversationIds: string[]) => {
    const body: ConversationIdsRequest = { conversationIds };
    return apiClient.post<void>("/analytics/delete", body);
  },
};
