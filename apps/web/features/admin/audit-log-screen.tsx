"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ChevronRight, ScrollText, SearchX } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { DataTable, type Column } from "@/components/data/data-table";
import { FilterChips, Pagination, SelectField, type Chip } from "@/components/data/list-controls";
import { NoValue } from "@/components/data/values";
import { sectionHref } from "@/components/shell/nav-config";
import { PageHeader } from "@/components/shell/page-header";
import { CopyButton } from "@/components/states/copy-button";
import { EmptyState } from "@/components/states/empty-state";
import { PermissionDenied } from "@/components/states/permission-denied";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { adminApi, adminKeys, type AuditEntry } from "@/lib/api/admin-api";
import { exceptionKeys, exceptionsApi } from "@/lib/api/exceptions-api";
import { formatDate, formatDateTimeShort, storeMidnight, zonedTimeToUtc, zoneGenericName } from "@/lib/format/datetime";
import { formatCount } from "@/lib/format/number";
import { useDocumentTitle } from "@/lib/hooks/use-document-title";
import { useListState } from "@/lib/hooks/use-list-state";
import { useNow } from "@/lib/hooks/use-now";
import { defineListParams } from "@/lib/list-params";
import { importTypeLabels, type ImportType } from "@/lib/status-maps";
import { useStore, type StoreContextValue } from "@/lib/store/store-context";
import { cn } from "@/lib/utils";

import { AUDIT_ACTION_GROUPS, AUDIT_ACTION_PREFIXES, auditActionLabel } from "./audit-actions";
import { FieldError } from "./form-parts";

const PERIODS = ["24h", "7d", "30d", "90d", "all", "custom"] as const;
type Period = (typeof PERIODS)[number];
const PERIOD_LABELS: Record<Period, string> = {
  "24h": "Last 24 hours",
  "7d": "Last 7 days",
  "30d": "Last 30 days",
  "90d": "Last 90 days",
  all: "All time",
  custom: "Custom range",
};
const PRESET_DAYS_BACK: Partial<Record<Period, number>> = { "7d": 6, "30d": 29, "90d": 89 };
const MINUTE = 60_000;
const DAY_KEY = /^\d{4}-\d{2}-\d{2}$/;

export const auditList = defineListParams(
  {
    period: { kind: "one", values: PERIODS, fallback: "7d" },
    from: { kind: "text", max: 10 },
    to: { kind: "text", max: 10 },
    action: { kind: "one", values: AUDIT_ACTION_PREFIXES },
    actor_user_id: { kind: "id" },
  },
  { sorts: ["-occurred_at"], defaultSort: "-occurred_at", pageSizes: [50, 100], defaultPageSize: 50 },
);

/** A real calendar day as `YYYY-MM-DD`, or `null`. */
export function validDay(value: string): string | null {
  if (!DAY_KEY.test(value)) return null;
  const date = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value ? value : null;
}

const nextDay = (day: string) => new Date(Date.parse(`${day}T00:00:00Z`) + 24 * 60 * MINUTE).toISOString().slice(0, 10);

/**
 * The `from` / `to` instants for the API (`to` exclusive). Presets count store-local calendar days
 * including today (BR-501); a custom range covers whole store-local days, either end optional.
 */
export function auditRange(
  period: Period,
  custom: { from: string; to: string },
  now: Date,
  timeZone: string,
): { from?: string; to?: string } {
  if (period === "all") return {};
  if (period === "24h") return { from: new Date(Math.floor(now.getTime() / MINUTE) * MINUTE - 24 * 60 * MINUTE).toISOString() };
  if (period === "custom") {
    const from = validDay(custom.from);
    const to = validDay(custom.to);
    return {
      from: from ? zonedTimeToUtc(from, "00:00", timeZone).toISOString() : undefined,
      to: to ? zonedTimeToUtc(nextDay(to), "00:00", timeZone).toISOString() : undefined,
    };
  }
  return { from: storeMidnight(now, timeZone, PRESET_DAYS_BACK[period] ?? 6).toISOString() };
}

type Target = { label: string; href?: string };

/** A readable label, and a link when the record belongs to this store (S-15 Target column). */
export function auditTarget(entry: AuditEntry, store: Pick<StoreContextValue, "id" | "permissions">): Target | null {
  if (!entry.target_type) return null;
  const id = entry.target_id ?? "";
  const short = id.slice(0, 8);
  const details = entry.details;
  const here = entry.store_id === store.id;
  const under = (segment: string, path: string) => {
    const base = here ? sectionHref(store.id, segment, store.permissions) : undefined;
    return base ? `${base}${path}` : undefined;
  };
  switch (entry.target_type) {
    case "exception":
      return { label: typeof details.reference === "string" ? details.reference : `Exception ${short}`, href: under("exceptions", `/${id}`) };
    case "data_import": {
      const type = details.import_type as ImportType | undefined;
      return { label: `${type && importTypeLabels[type] ? importTypeLabels[type] : "CSV"} import`, href: under("imports", `/${id}`) };
    }
    case "store":
      return { label: "Store settings", href: id === store.id ? sectionHref(store.id, "admin/settings", store.permissions) : undefined };
    case "user": {
      const name = typeof details.full_name === "string" ? details.full_name : id === entry.actor_user_id ? entry.actor_name : null;
      return { label: name ?? `Member ${short}` };
    }
    case "evaluation_run":
      return { label: `Analysis run ${short}` };
    default:
      return { label: `${entry.target_type} ${short}`.trim() };
  }
}

function TargetLabel({ target }: { target: Target | null }) {
  if (!target) return <NoValue />;
  return target.href ? (
    <Link href={target.href} className="hover:underline">
      {target.label}
    </Link>
  ) : (
    <span>{target.label}</span>
  );
}

const valueText = (value: unknown): string =>
  value === null || value === undefined ? "—" : typeof value === "object" ? JSON.stringify(value) : String(value);

/** The entry's metadata as a key–value list. A before/after pair is shown per key (settings). */
function AuditDetails({ entry, target }: { entry: AuditEntry; target: Target | null }) {
  const { before, after, ...rest } = entry.details as Record<string, unknown>;
  const isDiff = typeof before === "object" && before !== null && typeof after === "object" && after !== null;
  const rows: Array<[string, React.ReactNode]> = [];
  if (isDiff) {
    const keys = [...new Set([...Object.keys(before), ...Object.keys(after)])];
    for (const key of keys) {
      rows.push([key, `${valueText((before as Record<string, unknown>)[key])} → ${valueText((after as Record<string, unknown>)[key])}`]);
    }
  }
  const remaining = isDiff ? rest : (entry.details as Record<string, unknown>);
  for (const [key, value] of Object.entries(remaining)) rows.push([key, valueText(value)]);

  return (
    <div className="flex max-w-[calc(100vw-4rem)] flex-col gap-2 md:max-w-none">
      <dl className="grid grid-cols-1 gap-x-4 gap-y-1 text-sm sm:grid-cols-[max-content_minmax(0,1fr)]">
        <dt className="text-muted-foreground">Action code</dt>
        <dd className="font-mono text-xs break-all">{entry.action}</dd>
        <dt className="text-muted-foreground">Target</dt>
        <dd className="min-w-0 break-words">
          <TargetLabel target={target} />
        </dd>
        <dt className="text-muted-foreground">Request ID</dt>
        <dd className="font-mono text-xs break-all">{entry.request_id ?? "—"}</dd>
        {rows.map(([key, value]) => (
          <div key={key} className="contents">
            <dt className="font-mono text-xs text-muted-foreground">{key}</dt>
            <dd className="font-mono text-xs break-all whitespace-pre-wrap">{value}</dd>
          </div>
        ))}
      </dl>
      {rows.length === 0 ? <p className="text-sm text-muted-foreground">No further details were recorded.</p> : null}
    </div>
  );
}

/** Audit log (SCREEN_SPECIFICATIONS S-15): append-only, newest first, server-paginated. */
export function AuditLogScreen() {
  const store = useStore();
  const now = useNow();
  useDocumentTitle("Audit log");
  const canRead = store.permissions.has("audit.read");
  const { params, update, clearAll, isFiltered } = useListState(auditList);
  const zone = zoneGenericName(store.timezone);
  const period = (params.period ?? "7d") as Period;
  const [expanded, setExpanded] = useState<ReadonlySet<string>>(new Set());

  // Custom range inputs keep a draft, so an inverted range is explained instead of applied.
  const [draft, setDraft] = useState({ from: params.from, to: params.to });
  const [synced, setSynced] = useState({ from: params.from, to: params.to });
  if (synced.from !== params.from || synced.to !== params.to) {
    setSynced({ from: params.from, to: params.to });
    setDraft({ from: params.from, to: params.to });
  }
  const draftFrom = validDay(draft.from);
  const draftTo = validDay(draft.to);
  const rangeError = draftFrom && draftTo && draftFrom > draftTo ? "The start date must be on or before the end date." : undefined;
  const changeDraft = (patch: Partial<typeof draft>) => {
    const next = { ...draft, ...patch };
    setDraft(next);
    const from = validDay(next.from);
    const to = validDay(next.to);
    if (from && to && from > to) return;
    update({ from: from ?? "", to: to ?? "" });
  };

  const range = auditRange(period, { from: params.from, to: params.to }, now, store.timezone);
  const query = {
    action: params.action ?? undefined,
    actor_user_id: params.actor_user_id ?? undefined,
    from: range.from,
    to: range.to,
    page: params.page,
    page_size: params.page_size,
  };
  const list = useQuery({
    queryKey: adminKeys.auditLogs(store.id, query),
    queryFn: ({ signal }) => adminApi.auditLogs(store.id, query, signal),
    placeholderData: keepPreviousData,
    enabled: canRead,
  });
  // Actor filter options: the store's active members (names only, no emails).
  const members = useQuery({
    queryKey: exceptionKeys.members(store.id),
    queryFn: ({ signal }) => exceptionsApi.members(store.id, signal),
    enabled: canRead && store.permissions.has("exceptions.read"),
    staleTime: 5 * 60_000,
  });

  if (!canRead) return <PermissionDenied pageName="the audit log" permission="audit.read" />;

  const actorName = (id: string) =>
    members.data?.items.find((member) => member.id === id)?.full_name ??
    list.data?.items.find((entry) => entry.actor_user_id === id)?.actor_name ??
    "Selected member";
  const periodLabel =
    period === "custom"
      ? [params.from && `from ${formatDate(`${params.from}T12:00:00Z`, "UTC")}`, params.to && `to ${formatDate(`${params.to}T12:00:00Z`, "UTC")}`]
          .filter(Boolean)
          .join(" ") || "Custom range"
      : PERIOD_LABELS[period];
  const chips: Chip[] = [
    ...(period !== "7d" ? [{ key: "period", label: `Period: ${periodLabel}`, onRemove: () => update({ period: "7d", from: "", to: "" }) }] : []),
    ...(params.action
      ? [
          {
            key: "action",
            label: `Action: ${AUDIT_ACTION_GROUPS.find((group) => group.prefix === params.action)?.label ?? params.action}`,
            onRemove: () => update({ action: null }),
          },
        ]
      : []),
    ...(params.actor_user_id ? [{ key: "actor", label: `Actor: ${actorName(params.actor_user_id)}`, onRemove: () => update({ actor_user_id: null }) }] : []),
  ];

  const toggle = (id: string) =>
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const columns: Column<AuditEntry>[] = [
    {
      id: "time",
      header: `Time (${zone})`,
      pinned: true,
      cell: (entry) => {
        const open = expanded.has(entry.id);
        const time = formatDateTimeShort(entry.occurred_at, store.timezone, now);
        return (
          <span className="flex items-center gap-1 whitespace-nowrap">
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              aria-expanded={open}
              aria-controls={open ? `audit-details-${entry.id}` : undefined}
              aria-label={`${open ? "Hide" : "Show"} details: ${auditActionLabel(entry)}, ${time}`}
              onClick={() => toggle(entry.id)}
            >
              <ChevronRight aria-hidden className={cn("transition-transform duration-100", open && "rotate-90")} />
            </Button>
            <time dateTime={entry.occurred_at}>{time}</time>
          </span>
        );
      },
    },
    {
      id: "actor",
      header: "Actor",
      cell: (entry) =>
        entry.actor_name ? (
          <span className="whitespace-nowrap">{entry.actor_name}</span>
        ) : entry.actor_user_id ? (
          <span className="text-muted-foreground">Former member</span>
        ) : (
          "System"
        ),
    },
    {
      id: "action",
      header: "Action",
      cell: (entry) => (
        <span className="flex flex-col">
          <span>{auditActionLabel(entry)}</span>
          <code className="font-mono text-xs text-muted-foreground">{entry.action}</code>
        </span>
      ),
    },
    { id: "target", header: "Target", hideBelow: "md", cell: (entry) => <TargetLabel target={auditTarget(entry, store)} /> },
    {
      id: "request",
      header: "Request ID",
      hideBelow: "lg",
      cell: (entry) =>
        entry.request_id ? (
          <span className="flex items-center gap-1">
            <code className="max-w-40 truncate font-mono text-xs" title={entry.request_id}>
              {entry.request_id}
            </code>
            <CopyButton value={entry.request_id} label="Copy request ID" />
          </span>
        ) : (
          <NoValue />
        ),
    },
  ];

  const total = list.data?.total ?? 0;
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Audit log" subtitle={`${store.name} · append-only`} />
      <section aria-label="Audit events" className="rounded-lg border bg-card">
        <div className="flex flex-col gap-3 border-b p-4">
          <div className="flex flex-wrap items-center gap-3">
            <SelectField
              label="Period"
              value={period}
              options={PERIODS.map((value) => ({ value, label: PERIOD_LABELS[value] }))}
              onChange={(value) => update({ period: value, from: "", to: "" })}
            />
            <SelectField
              label="Action"
              value={params.action ?? ""}
              options={[{ value: "", label: "All actions" }, ...AUDIT_ACTION_GROUPS.map((group) => ({ value: group.prefix, label: group.label }))]}
              onChange={(value) => update({ action: value || null })}
            />
            <SelectField
              label="Actor"
              value={params.actor_user_id ?? ""}
              options={[
                { value: "", label: "Anyone" },
                ...(params.actor_user_id && !members.data?.items.some((member) => member.id === params.actor_user_id)
                  ? [{ value: params.actor_user_id, label: actorName(params.actor_user_id) }]
                  : []),
                ...(members.data?.items ?? []).map((member) => ({ value: member.id, label: member.full_name })),
              ]}
              onChange={(value) => update({ actor_user_id: value || null })}
            />
            <p className="ml-auto text-sm text-muted-foreground" aria-live="polite">
              {list.data ? formatCount(total, "event") : null}
            </p>
          </div>
          {period === "custom" ? (
            <fieldset className="flex flex-col gap-2">
              <legend className="sr-only">Custom date range ({zone})</legend>
              <div className="flex flex-wrap items-end gap-3">
                <div className="flex flex-col gap-1">
                  <Label htmlFor="audit-from">From</Label>
                  <Input
                    id="audit-from"
                    type="date"
                    className="w-full sm:w-44"
                    value={draft.from}
                    aria-invalid={rangeError ? true : undefined}
                    aria-describedby={rangeError ? "audit-range-error" : undefined}
                    onChange={(event) => changeDraft({ from: event.target.value })}
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <Label htmlFor="audit-to">To</Label>
                  <Input
                    id="audit-to"
                    type="date"
                    className="w-full sm:w-44"
                    value={draft.to}
                    aria-invalid={rangeError ? true : undefined}
                    aria-describedby={rangeError ? "audit-range-error" : undefined}
                    onChange={(event) => changeDraft({ to: event.target.value })}
                  />
                </div>
                <p className="text-sm text-muted-foreground">Whole days in {zone}. Leave a date empty for an open range.</p>
              </div>
              <FieldError id="audit-range-error" message={rangeError} />
            </fieldset>
          ) : null}
          <FilterChips chips={chips} onClearAll={clearAll} />
        </div>
        <DataTable
          caption={`Audit events, page ${params.page}, newest first`}
          columns={columns}
          rows={list.data?.items}
          getRowId={(entry) => entry.id}
          status={list.isPending ? "loading" : list.isError ? "error" : "success"}
          isFetching={list.isPlaceholderData}
          error={list.error}
          onRetry={() => void list.refetch()}
          errorTitle="Couldn't load the audit log"
          isFiltered={isFiltered}
          density="compact"
          renderExpanded={(entry) =>
            expanded.has(entry.id) ? (
              <div id={`audit-details-${entry.id}`}>
                <AuditDetails entry={entry} target={auditTarget(entry, store)} />
              </div>
            ) : null
          }
          noResults={
            <EmptyState
              icon={SearchX}
              title="No audit events match these filters"
              action={
                <Button type="button" variant="secondary" onClick={clearAll}>
                  Clear filters
                </Button>
              }
            />
          }
          empty={
            <EmptyState
              icon={ScrollText}
              title="No audit events in this period"
              description="Nothing was recorded in the last 7 days. Widen the date range to see older events."
              action={
                <Button type="button" variant="secondary" onClick={() => update({ period: "all" })}>
                  Show all time
                </Button>
              }
            />
          }
        />
        {list.data && total > 0 ? (
          <Pagination
            page={params.page}
            pageSize={params.page_size}
            total={total}
            onPageChange={(page) => update({ page }, "push")}
            onPageSizeChange={(page_size) => update({ page_size })}
            pageSizes={auditList.options.pageSizes}
          />
        ) : null}
      </section>
    </div>
  );
}
