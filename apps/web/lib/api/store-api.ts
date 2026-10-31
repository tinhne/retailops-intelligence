import type { Schema } from "@retailops/contracts";

import { apiFetch, type QueryParams } from "./client";

export type Dashboard = Schema<"DashboardOut">;
export type AttentionItem = Schema<"AttentionItem">;
export type Trends = Schema<"TrendsOut">;
export type ImportPage = Schema<"Page_ImportOut_">;
export type ExceptionPage = Schema<"Page_ExceptionListItem_">;
export type EvaluationRun = Schema<"EvaluationRunOut">;
export type ExceptionStatusFilter = Schema<"ExceptionStatus">;

const store = (storeId: string) => `/stores/${storeId}`;

export const storeApi = {
  dashboard: (storeId: string, signal?: AbortSignal) =>
    apiFetch<Dashboard>(`${store(storeId)}/analytics/dashboard`, { signal }),

  trends: (storeId: string, days: number, signal?: AbortSignal) =>
    apiFetch<Trends>(`${store(storeId)}/analytics/trends`, { query: { days }, signal }),

  /** Exceptions list. Without `status` the API returns the active statuses. */
  exceptions: (storeId: string, query: QueryParams, signal?: AbortSignal) =>
    apiFetch<ExceptionPage>(`${store(storeId)}/exceptions`, { query, signal }),

  imports: (storeId: string, query: QueryParams, signal?: AbortSignal) =>
    apiFetch<ImportPage>(`${store(storeId)}/imports`, { query, signal }),

  /** Runs a manual evaluation synchronously (ADR-0009). The key makes a retried click safe. */
  runEvaluation: (storeId: string, idempotencyKey: string) =>
    apiFetch<EvaluationRun>(`${store(storeId)}/evaluations`, {
      method: "POST",
      body: {},
      headers: { "Idempotency-Key": idempotencyKey },
    }),

  evaluation: (storeId: string, runId: string, signal?: AbortSignal) =>
    apiFetch<EvaluationRun>(`${store(storeId)}/evaluations/${runId}`, { signal }),
};

/** Query keys always start with the store (IA §7), so switching stores never shows stale data. */
export const storeKeys = {
  all: (storeId: string) => ["store", storeId] as const,
  dashboard: (storeId: string) => ["store", storeId, "dashboard"] as const,
  trends: (storeId: string, days: number) => ["store", storeId, "trends", days] as const,
  exceptions: (storeId: string, query: QueryParams) => ["store", storeId, "exceptions", query] as const,
  imports: (storeId: string, query: QueryParams) => ["store", storeId, "imports", query] as const,
};
