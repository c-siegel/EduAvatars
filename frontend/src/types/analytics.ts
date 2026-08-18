export interface AnalyticsStats {
  sessions: number;
  sessionsDeltaPct: number;
  messages: number;
  messagesDeltaPct: number;
  avgDurationSeconds: number;
  avgDurationDeltaPct: number;
  tokenCostEur: number;
  tokenCostDeltaPct: number;
}

export interface SessionRow {
  id: string;
  projectTitle: string;
  startedAt: string;
  messageCount: number;
  durationSeconds: number;
  lastQuestion: string | null;
}

export interface SessionsPage {
  items: SessionRow[];
  total: number;
}

export type Granularity = "day" | "week" | "month";

export interface TimeseriesPoint {
  label: string;
  value: number;
}

export interface AnalyticsFilters {
  projectId: string | null;
  periodDays: number;
  model: string | null;
}
