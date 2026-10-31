import type { QueryParams } from "@/lib/api/client";
import type {
  ExceptionCategory,
  ExceptionStatus,
  ExceptionType,
  PriorityBand,
  Severity,
} from "@/lib/status-maps";
import { exceptionTypeLabels } from "@/lib/status-maps";

// URL state for the exceptions inbox (S-03, IA §9). Filters live in the URL so a view can be
// shared and survives reload. Unknown values are dropped and reported, never sent to the API.

export const VIEWS = ["active", "triage", "mine", "unassigned", "closed"] as const;
export type View = (typeof VIEWS)[number];

export const SEVERITIES: Severity[] = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];
export const BANDS: PriorityBand[] = ["P1", "P2", "P3", "P4"];
export const CATEGORIES: ExceptionCategory[] = ["INVENTORY", "FULFILLMENT", "PAYMENT", "DATA_QUALITY"];
export const TYPES = Object.keys(exceptionTypeLabels) as ExceptionType[];
export const SORTS = ["-priority_score", "due_at", "-first_detected_at", "-last_detected_at"] as const;
export type Sort = (typeof SORTS)[number];
export const DUES = ["overdue", "24h"] as const;
export type Due = (typeof DUES)[number];
export const PAGE_SIZES = [25, 50, 100] as const;
export type PageSize = (typeof PAGE_SIZES)[number];

export const ACTIVE_STATUSES: ExceptionStatus[] = ["OPEN", "ACKNOWLEDGED", "IN_PROGRESS", "REOPENED"];
export const CLOSED_STATUSES: ExceptionStatus[] = ["RESOLVED", "DISMISSED"];

/** Statuses each view covers; the Status filter can only narrow within them. */
export const VIEW_STATUSES: Record<View, ExceptionStatus[]> = {
  active: ACTIVE_STATUSES,
  triage: ["OPEN", "REOPENED"],
  mine: ACTIVE_STATUSES,
  unassigned: ACTIVE_STATUSES,
  closed: CLOSED_STATUSES,
};

export const VIEW_DEFAULT_SORT: Record<View, Sort> = {
  active: "-priority_score",
  triage: "-priority_score",
  mine: "-priority_score",
  unassigned: "-priority_score",
  closed: "-first_detected_at",
};

export type InboxParams = {
  view: View;
  q: string;
  severity: Severity[];
  priority_band: PriorityBand[];
  status: ExceptionStatus[];
  category: ExceptionCategory[];
  exception_type: ExceptionType[];
  /** "me", "unassigned" or a member id. Only used in views that don't fix the assignee. */
  assignee: string | null;
  due: Due | null;
  sort: Sort;
  page: number;
  page_size: PageSize;
};

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function pickAll<T extends string>(values: string[], allowed: readonly T[], invalid: string[], key: string): T[] {
  const picked: T[] = [];
  for (const value of values) {
    if ((allowed as readonly string[]).includes(value)) {
      if (!picked.includes(value as T)) picked.push(value as T);
    } else invalid.push(key);
  }
  return picked;
}

function pickOne<T extends string>(value: string | null, allowed: readonly T[], invalid: string[], key: string): T | null {
  if (value === null || value === "") return null;
  if ((allowed as readonly string[]).includes(value)) return value as T;
  invalid.push(key);
  return null;
}

/**
 * Parses and validates the inbox URL. `defaultView` applies when `view` is absent (STAFF start
 * in "Assigned to me", everyone else in "All active").
 */
export function parseInboxParams(search: URLSearchParams, defaultView: View = "active") {
  const invalid: string[] = [];
  const view = pickOne(search.get("view"), VIEWS, invalid, "view") ?? defaultView;
  const statusesInView = VIEW_STATUSES[view];
  const status = pickAll(search.getAll("status"), statusesInView, invalid, "status");
  const assigneeRaw = search.get("assignee");
  let assignee: string | null = null;
  if (assigneeRaw) {
    if (assigneeRaw === "me" || assigneeRaw === "unassigned" || UUID.test(assigneeRaw)) assignee = assigneeRaw;
    else invalid.push("assignee");
  }
  const page = Number(search.get("page") ?? "1");
  const pageSize = Number(search.get("page_size") ?? "25");
  if (search.has("page") && !(Number.isInteger(page) && page >= 1)) invalid.push("page");
  if (search.has("page_size") && !(PAGE_SIZES as readonly number[]).includes(pageSize)) invalid.push("page_size");

  const params: InboxParams = {
    view,
    q: (search.get("q") ?? "").slice(0, 100),
    severity: pickAll(search.getAll("severity"), SEVERITIES, invalid, "severity"),
    priority_band: pickAll(search.getAll("priority_band"), BANDS, invalid, "priority_band"),
    status,
    category: pickAll(search.getAll("category"), CATEGORIES, invalid, "category"),
    exception_type: pickAll(search.getAll("exception_type"), TYPES, invalid, "exception_type"),
    assignee: view === "mine" || view === "unassigned" ? null : assignee,
    due: pickOne(search.get("due"), DUES, invalid, "due"),
    sort: pickOne(search.get("sort"), SORTS, invalid, "sort") ?? VIEW_DEFAULT_SORT[view],
    page: Number.isInteger(page) && page >= 1 ? page : 1,
    page_size: (PAGE_SIZES as readonly number[]).includes(pageSize) ? (pageSize as PageSize) : 25,
  };
  return { params, invalid };
}

/** Back to URL form, leaving out defaults so links stay short. */
export function serializeInboxParams(params: InboxParams): URLSearchParams {
  const search = new URLSearchParams();
  search.set("view", params.view);
  if (params.q) search.set("q", params.q);
  for (const key of ["severity", "priority_band", "status", "category", "exception_type"] as const) {
    for (const value of params[key]) search.append(key, value);
  }
  if (params.assignee) search.set("assignee", params.assignee);
  if (params.due) search.set("due", params.due);
  if (params.sort !== VIEW_DEFAULT_SORT[params.view]) search.set("sort", params.sort);
  if (params.page !== 1) search.set("page", String(params.page));
  if (params.page_size !== 25) search.set("page_size", String(params.page_size));
  return search;
}

/** The API query for the inbox: the view preset combined with the person's filters. */
export function toApiQuery(params: InboxParams, now: Date): QueryParams {
  const query: QueryParams = {
    status: params.status.length > 0 ? params.status : VIEW_STATUSES[params.view],
    severity: params.severity,
    priority_band: params.priority_band,
    category: params.category,
    exception_type: params.exception_type,
    q: params.q.trim() || undefined,
    sort: params.sort,
    page: params.page,
    page_size: params.page_size,
  };
  if (params.view === "mine") query.assignee = "me";
  else if (params.view === "unassigned") query.assignee = "unassigned";
  else if (params.assignee) query.assignee = params.assignee;
  if (params.due === "overdue") query.due_to = now.toISOString();
  if (params.due === "24h") query.due_to = new Date(now.getTime() + 24 * 3_600_000).toISOString();
  return query;
}

/** Whether anything narrows the view (decides "No results" versus "Empty", S-03). */
export function isFiltered(params: InboxParams): boolean {
  return Boolean(
    params.q.trim() ||
      params.severity.length ||
      params.priority_band.length ||
      params.status.length ||
      params.category.length ||
      params.exception_type.length ||
      params.assignee ||
      params.due,
  );
}

/** Applies a change and resets to page 1 unless the page itself is changing (C-30). */
export function updateParams(params: InboxParams, patch: Partial<InboxParams>): InboxParams {
  const next = { ...params, ...patch };
  if (!("page" in patch)) next.page = 1;
  if ("view" in patch && patch.view !== params.view) {
    next.status = [];
    next.sort = VIEW_DEFAULT_SORT[next.view];
    if (next.view === "mine" || next.view === "unassigned") next.assignee = null;
  }
  return next;
}

/** "EXC-1042" or "1042": an exact reference typed into the search box. */
export function exactReference(q: string): string | null {
  const match = q.trim().toUpperCase().match(/^(?:EXC-)?(\d{1,9})$/);
  return match ? `EXC-${match[1]}` : null;
}
