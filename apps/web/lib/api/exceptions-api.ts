import type { Schema } from "@retailops/contracts";

import { apiFetch, type QueryParams } from "./client";

export type ExceptionDetail = Schema<"ExceptionDetail">;
export type ExceptionListItem = Schema<"ExceptionListItem">;
export type ExceptionEvent = Schema<"ExceptionEventOut">;
export type ExceptionNote = Schema<"ExceptionNoteOut">;
export type ExceptionActionName = Schema<"ExceptionAction">;
export type Member = Schema<"MemberOut">;
export type ResolveBody = Omit<Schema<"ResolveRequest">, "expected_version">;
export type DismissBody = Omit<Schema<"DismissRequest">, "expected_version">;
export type ReopenBody = Omit<Schema<"ReopenRequest">, "expected_version">;
export type DueDateBody = Omit<Schema<"DueDateRequest">, "expected_version">;

const base = (storeId: string, exceptionId: string) => `/stores/${storeId}/exceptions/${exceptionId}`;

/**
 * Lifecycle commands. Every one carries `expected_version`, the version on screen, so a change
 * made by someone else in the meantime returns `409 STALE_VERSION` instead of being overwritten.
 */
export const exceptionsApi = {
  detail: (storeId: string, id: string, signal?: AbortSignal) =>
    apiFetch<ExceptionDetail>(base(storeId, id), { signal }),
  events: (storeId: string, id: string, query: QueryParams, signal?: AbortSignal) =>
    apiFetch<Schema<"Page_ExceptionEventOut_">>(`${base(storeId, id)}/events`, { query, signal }),
  notes: (storeId: string, id: string, query: QueryParams, signal?: AbortSignal) =>
    apiFetch<Schema<"Page_ExceptionNoteOut_">>(`${base(storeId, id)}/notes`, { query, signal }),
  members: (storeId: string, signal?: AbortSignal) =>
    apiFetch<Schema<"MemberList">>(`/stores/${storeId}/members`, { signal }),

  acknowledge: (storeId: string, id: string, version: number) =>
    apiFetch<ExceptionDetail>(`${base(storeId, id)}/acknowledge`, { method: "POST", body: { expected_version: version } }),
  start: (storeId: string, id: string, version: number) =>
    apiFetch<ExceptionDetail>(`${base(storeId, id)}/start`, { method: "POST", body: { expected_version: version } }),
  /** Assign, reassign, claim (assign to oneself) or unassign (`null`). */
  assign: (storeId: string, id: string, version: number, assigneeId: string | null) =>
    apiFetch<ExceptionDetail>(`${base(storeId, id)}/assign`, {
      method: "POST",
      body: { assignee_id: assigneeId, expected_version: version },
    }),
  resolve: (storeId: string, id: string, version: number, body: ResolveBody) =>
    apiFetch<ExceptionDetail>(`${base(storeId, id)}/resolve`, { method: "POST", body: { ...body, expected_version: version } }),
  dismiss: (storeId: string, id: string, version: number, body: DismissBody) =>
    apiFetch<ExceptionDetail>(`${base(storeId, id)}/dismiss`, { method: "POST", body: { ...body, expected_version: version } }),
  reopen: (storeId: string, id: string, version: number, body: ReopenBody) =>
    apiFetch<ExceptionDetail>(`${base(storeId, id)}/reopen`, { method: "POST", body: { ...body, expected_version: version } }),
  setDueDate: (storeId: string, id: string, version: number, body: DueDateBody) =>
    apiFetch<ExceptionDetail>(`${base(storeId, id)}/due-date`, { method: "PATCH", body: { ...body, expected_version: version } }),
  addNote: (storeId: string, id: string, version: number, body: string) =>
    apiFetch<ExceptionNote>(`${base(storeId, id)}/notes`, { method: "POST", body: { body, expected_version: version } }),
};

export const exceptionKeys = {
  all: (storeId: string) => ["store", storeId, "exceptions"] as const,
  detail: (storeId: string, id: string) => ["store", storeId, "exceptions", "detail", id] as const,
  events: (storeId: string, id: string) => ["store", storeId, "exceptions", "detail", id, "events"] as const,
  notes: (storeId: string, id: string) => ["store", storeId, "exceptions", "detail", id, "notes"] as const,
  members: (storeId: string) => ["store", storeId, "members"] as const,
};
