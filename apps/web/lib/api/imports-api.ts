import type { Schema } from "@retailops/contracts";

import { apiFetch, type QueryParams } from "./client";

export type ImportItem = Schema<"ImportOut">;
export type ImportDetail = Schema<"ImportDetailOut">;
export type ImportIssue = Schema<"ImportIssueOut">;
export type ImportSummary = Schema<"ImportSummary">;
export type PreviewRow = Schema<"PreviewRow">;
export type ApplyImportRequest = Schema<"ApplyImportRequest">;

const base = (storeId: string) => `/stores/${storeId}/imports`;

/** CSV imports (S-11..S-13, IMPORT_PIPELINE). Upload validates in the same request. */
export const importsApi = {
  list: (storeId: string, query: QueryParams, signal?: AbortSignal) =>
    apiFetch<Schema<"Page_ImportOut_">>(base(storeId), { query, signal }),
  get: (storeId: string, importId: string, signal?: AbortSignal) =>
    apiFetch<ImportDetail>(`${base(storeId)}/${importId}`, { signal }),
  issues: (storeId: string, importId: string, query: QueryParams, signal?: AbortSignal) =>
    apiFetch<Schema<"Page_ImportIssueOut_">>(`${base(storeId)}/${importId}/issues`, { query, signal }),
  upload: (storeId: string, importType: string, file: File) => {
    const form = new FormData();
    form.append("import_type", importType);
    form.append("file", file);
    return apiFetch<ImportDetail>(base(storeId), { method: "POST", body: form });
  },
  /** The key is reused when the same attempt is retried, so a retry never applies twice. */
  apply: (storeId: string, importId: string, body: ApplyImportRequest, idempotencyKey: string) =>
    apiFetch<ImportDetail>(`${base(storeId)}/${importId}/apply`, {
      method: "POST",
      body,
      headers: { "Idempotency-Key": idempotencyKey },
    }),
  discard: (storeId: string, importId: string) =>
    apiFetch<ImportDetail>(`${base(storeId)}/${importId}/discard`, { method: "POST", body: {} }),
  templatePath: (storeId: string, importType: string) => `${base(storeId)}/templates/${importType}`,
  issuesCsvPath: (storeId: string, importId: string) => `${base(storeId)}/${importId}/issues.csv`,
};

/** Keys share the `imports` prefix with the Overview's recent imports, so one invalidation refreshes both. */
export const importKeys = {
  all: (storeId: string) => ["store", storeId, "imports"] as const,
  list: (storeId: string, query: QueryParams) => ["store", storeId, "imports", query] as const,
  detail: (storeId: string, importId: string) => ["store", storeId, "imports", "detail", importId] as const,
  issues: (storeId: string, importId: string, query: QueryParams) =>
    ["store", storeId, "imports", "detail", importId, "issues", query] as const,
};
