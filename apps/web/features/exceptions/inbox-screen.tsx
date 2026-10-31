"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { CircleCheck, Inbox, SearchX } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef } from "react";
import { toast } from "sonner";

import { DataTable } from "@/components/data/data-table";
import { FilterChips, MultiSelectFilter, Pagination, SearchInput, SelectField, type Chip, type Option } from "@/components/data/list-controls";
import { DateTime } from "@/components/data/values";
import { PageHeader } from "@/components/shell/page-header";
import { sectionHref } from "@/components/shell/nav-config";
import { EmptyState } from "@/components/states/empty-state";
import { PermissionDenied } from "@/components/states/permission-denied";
import { Button } from "@/components/ui/button";
import { exceptionKeys, exceptionsApi } from "@/lib/api/exceptions-api";
import { storeApi, storeKeys } from "@/lib/api/store-api";
import { formatRelative } from "@/lib/format/datetime";
import { formatCount, formatQuantity } from "@/lib/format/number";
import { useDocumentTitle } from "@/lib/hooks/use-document-title";
import { useNow } from "@/lib/hooks/use-now";
import {
  categoryLabels,
  exceptionStatusLabels,
  exceptionTypeCategory,
  exceptionTypeLabels,
  severityMeta,
} from "@/lib/status-maps";
import { useStore } from "@/lib/store/store-context";
import { cn } from "@/lib/utils";

import { RunAnalysisButton } from "../evaluations/run-analysis-button";
import { exceptionColumns, StackedExceptionRow } from "./exception-rows";
import {
  BANDS,
  CATEGORIES,
  exactReference,
  isFiltered,
  parseInboxParams,
  serializeInboxParams,
  SEVERITIES,
  toApiQuery,
  TYPES,
  updateParams,
  VIEW_STATUSES,
  type InboxParams,
  type View,
} from "./inbox-params";

export const LAST_LIST_KEY = "ro.exceptions.lastList";

const VIEW_LABELS: Record<View, string> = {
  active: "All active",
  triage: "Triage",
  mine: "Assigned to me",
  unassigned: "Unassigned",
  closed: "Closed",
};

const DUE_LABELS = { overdue: "Overdue", "24h": "Due within 24 h" } as const;
const SORT_OPTIONS: Option[] = [
  { value: "-priority_score", label: "Priority" },
  { value: "due_at", label: "Due soonest" },
  { value: "-first_detected_at", label: "Newest" },
  { value: "-last_detected_at", label: "Last detected" },
];

/** Total of a filtered list, from a one-row page, for the tab counts. */
function useCount(storeId: string, query: Record<string, string | string[]>, enabled: boolean) {
  const params = { ...query, page_size: 1 };
  return useQuery({
    queryKey: storeKeys.exceptions(storeId, params),
    queryFn: ({ signal }) => storeApi.exceptions(storeId, params, signal),
    select: (page) => page.total,
    enabled,
  });
}

/** The work queue (SCREEN_SPECIFICATIONS S-03). */
export function InboxScreen() {
  const store = useStore();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const now = useNow();
  useDocumentTitle("Exceptions");

  const canRead = store.permissions.has("exceptions.read");
  const canWork = store.permissions.has("exceptions.work");
  const defaultView: View = store.role === "STAFF" && canWork ? "mine" : "active";
  const { params, invalid } = useMemo(() => parseInboxParams(searchParams, defaultView), [searchParams, defaultView]);
  const mineUnavailable = params.view === "mine" && !canWork;

  const navigate = useCallback(
    (next: InboxParams, mode: "replace" | "push" = "replace") => {
      const url = `${pathname}?${serializeInboxParams(next).toString()}`;
      if (mode === "push") router.push(url, { scroll: false });
      else router.replace(url, { scroll: false });
    },
    [pathname, router],
  );
  const update = (patch: Partial<InboxParams>, mode: "replace" | "push" = "replace") => navigate(updateParams(params, patch), mode);

  // Unknown values in a shared link are dropped and the URL normalised (S-03 "Validation error").
  const normalised = useRef(false);
  useEffect(() => {
    if (normalised.current) return;
    if (invalid.length > 0) {
      normalised.current = true;
      toast.info("Some filters in the link weren't recognised and were removed.");
      navigate(params);
    } else if (mineUnavailable) {
      normalised.current = true;
      toast.info("Assigned to me is available to roles that work on exceptions.");
      navigate(updateParams(params, { view: "active" }));
    }
  }, [invalid.length, mineUnavailable, navigate, params]);

  // The detail page's breadcrumb returns to the list exactly as the person left it.
  useEffect(() => {
    try {
      window.sessionStorage.setItem(LAST_LIST_KEY, `${pathname}?${serializeInboxParams(params).toString()}`);
    } catch {
      // Storage unavailable: the breadcrumb falls back to the default view.
    }
  }, [pathname, params]);

  const minute = Math.floor(now.getTime() / 60_000);
  const apiQuery = useMemo(() => toApiQuery(params, new Date(minute * 60_000)), [params, minute]);
  const list = useQuery({
    queryKey: storeKeys.exceptions(store.id, apiQuery),
    queryFn: ({ signal }) => storeApi.exceptions(store.id, apiQuery, signal),
    placeholderData: keepPreviousData,
    refetchInterval: 60_000,
    enabled: canRead && !mineUnavailable,
  });
  const triageCount = useCount(store.id, { status: ["OPEN", "REOPENED"] }, canRead);
  const mineCount = useCount(store.id, { assignee: "me" }, canRead && canWork);
  const members = useQuery({
    queryKey: exceptionKeys.members(store.id),
    queryFn: ({ signal }) => exceptionsApi.members(store.id, signal),
    enabled: canRead,
    staleTime: 5 * 60_000,
  });
  const dashboard = useQuery({
    queryKey: storeKeys.dashboard(store.id),
    queryFn: ({ signal }) => storeApi.dashboard(store.id, signal),
    enabled: store.permissions.has("dashboard.read"),
  });

  if (!canRead) return <PermissionDenied pageName="exceptions" permission="exceptions.read" />;

  const lastRun = dashboard.data?.data_freshness.last_evaluation_run;
  const workers = (members.data?.items ?? []).filter((member) => member.can_work_exceptions);
  const memberName = (id: string) => workers.find((member) => member.id === id)?.full_name ?? "Selected member";
  const assigneeLabel = (value: string) => (value === "me" ? "Me" : value === "unassigned" ? "Unassigned" : memberName(value));
  const hrefFor = (id: string) => `/s/${store.id}/exceptions/${id}`;
  const closedView = params.view === "closed";
  const filtered = isFiltered(params);
  const reference = exactReference(params.q);
  const exactMatch =
    reference && list.data?.items.length === 1 && list.data.items[0].reference === reference ? list.data.items[0] : undefined;

  const chips: Chip[] = [
    ...(params.q ? [{ key: "q", label: `Search: ${params.q}`, onRemove: () => update({ q: "" }) }] : []),
    ...(params.severity.length
      ? [{ key: "severity", label: `Severity: ${params.severity.map((s) => severityMeta[s].label).join(", ")}`, onRemove: () => update({ severity: [] }) }]
      : []),
    ...(params.priority_band.length
      ? [{ key: "priority", label: `Priority: ${params.priority_band.join(", ")}`, onRemove: () => update({ priority_band: [] }) }]
      : []),
    ...(params.status.length
      ? [{ key: "status", label: `Status: ${params.status.map((s) => exceptionStatusLabels[s]).join(", ")}`, onRemove: () => update({ status: [] }) }]
      : []),
    ...(params.category.length
      ? [{ key: "category", label: `Category: ${params.category.map((c) => categoryLabels[c]).join(", ")}`, onRemove: () => update({ category: [] }) }]
      : []),
    ...(params.exception_type.length
      ? [{ key: "type", label: `Type: ${params.exception_type.map((t) => exceptionTypeLabels[t]).join(", ")}`, onRemove: () => update({ exception_type: [] }) }]
      : []),
    ...(params.assignee ? [{ key: "assignee", label: `Assignee: ${assigneeLabel(params.assignee)}`, onRemove: () => update({ assignee: null }) }] : []),
    ...(params.due ? [{ key: "due", label: `Due: ${DUE_LABELS[params.due]}`, onRemove: () => update({ due: null }) }] : []),
  ];

  const total = list.data?.total ?? 0;
  const views: View[] = canWork ? ["active", "triage", "mine", "unassigned", "closed"] : ["active", "triage", "unassigned", "closed"];

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Exceptions"
        meta={
          lastRun ? (
            <>
              Last evaluation <DateTime value={lastRun.started_at} compact /> ({formatRelative(lastRun.started_at, store.timezone, now)})
            </>
          ) : undefined
        }
        actions={<RunAnalysisButton running={lastRun?.status === "RUNNING"} />}
      />

      <nav aria-label="Exception views" className="-mx-(--page-gutter) overflow-x-auto px-(--page-gutter)">
        <ul className="flex min-w-max gap-1 border-b">
          {views.map((view) => {
            const count = view === "triage" ? triageCount.data : view === "mine" ? mineCount.data : undefined;
            const current = params.view === view;
            return (
              <li key={view}>
                <Link
                  href={`${pathname}?${serializeInboxParams(updateParams(params, { view, q: "", severity: [], priority_band: [], category: [], exception_type: [], assignee: null, due: null })).toString()}`}
                  aria-current={current ? "page" : undefined}
                  className={cn(
                    "-mb-px flex h-9 items-center gap-1.5 border-b-2 px-3 text-body-strong whitespace-nowrap transition-colors duration-100",
                    current ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground",
                  )}
                >
                  {VIEW_LABELS[view]}
                  {count !== undefined ? (
                    <span className="rounded-full bg-tone-neutral-bg px-1.5 text-xs text-tone-neutral-fg tabular-nums" aria-label={`, ${count}`}>
                      {formatQuantity(count)}
                    </span>
                  ) : null}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      <section aria-label="Exception list" className="rounded-lg border bg-card">
        <div className="flex flex-col gap-3 border-b p-4">
          <div className="flex flex-wrap items-center gap-2">
            <SearchInput label="Search exceptions" placeholder="Search reference or title" value={params.q} onChange={(q) => update({ q })} />
            <MultiSelectFilter
              label="Severity"
              options={SEVERITIES.map((s) => ({ value: s, label: severityMeta[s].label }))}
              selected={params.severity}
              onChange={(values) => update({ severity: values as InboxParams["severity"] })}
            />
            <MultiSelectFilter
              label="Priority"
              options={BANDS.map((band) => ({ value: band, label: band }))}
              selected={params.priority_band}
              onChange={(values) => update({ priority_band: values as InboxParams["priority_band"] })}
            />
            <MultiSelectFilter
              label="Status"
              options={VIEW_STATUSES[params.view].map((s) => ({ value: s, label: exceptionStatusLabels[s] }))}
              selected={params.status}
              onChange={(values) => update({ status: values as InboxParams["status"] })}
            />
            <MultiSelectFilter
              label="Category"
              options={CATEGORIES.map((c) => ({ value: c, label: categoryLabels[c] }))}
              selected={params.category}
              onChange={(values) => update({ category: values as InboxParams["category"] })}
            />
            <MultiSelectFilter
              label="Type"
              options={TYPES.map((t) => ({ value: t, label: exceptionTypeLabels[t], group: categoryLabels[exceptionTypeCategory[t]] }))}
              selected={params.exception_type}
              onChange={(values) => update({ exception_type: values as InboxParams["exception_type"] })}
            />
          </div>
          <div className="flex flex-wrap items-center gap-3">
            {params.view !== "mine" && params.view !== "unassigned" ? (
              <SelectField
                label="Assignee"
                value={params.assignee ?? ""}
                options={[
                  { value: "", label: "Anyone" },
                  ...(canWork ? [{ value: "me", label: "Me" }] : []),
                  { value: "unassigned", label: "Unassigned" },
                  ...workers.map((member) => ({ value: member.id, label: member.full_name })),
                ]}
                onChange={(value) => update({ assignee: value || null })}
              />
            ) : null}
            {!closedView ? (
              <SelectField
                label="Due"
                value={params.due ?? ""}
                options={[{ value: "", label: "Any time" }, { value: "overdue", label: DUE_LABELS.overdue }, { value: "24h", label: DUE_LABELS["24h"] }]}
                onChange={(value) => update({ due: (value || null) as InboxParams["due"] })}
              />
            ) : null}
            <SelectField
              label="Sort"
              value={params.sort}
              options={SORT_OPTIONS}
              onChange={(value) => update({ sort: value as InboxParams["sort"] })}
            />
            <p className="ml-auto text-sm text-muted-foreground" aria-live="polite">
              {list.data ? formatCount(total, "exception") : null}
            </p>
          </div>
          <FilterChips
            chips={chips}
            onClearAll={() => update({ q: "", severity: [], priority_band: [], status: [], category: [], exception_type: [], assignee: null, due: null })}
          />
          {exactMatch ? (
            <p className="text-sm text-muted-foreground">
              <Link href={hrefFor(exactMatch.id)} className="text-link hover:underline">
                Open {exactMatch.reference}
              </Link>{" "}
              (exact reference match)
            </p>
          ) : null}
        </div>

        <DataTable
          caption={`Exceptions, ${VIEW_LABELS[params.view]}, page ${params.page}, sorted by ${SORT_OPTIONS.find((o) => o.value === params.sort)?.label ?? "priority"}`}
          columns={exceptionColumns((item) => hrefFor(item.id), closedView)}
          rows={list.data?.items}
          getRowId={(item) => item.id}
          status={list.isPending ? "loading" : list.isError ? "error" : "success"}
          isFetching={list.isPlaceholderData}
          error={list.error}
          onRetry={() => void list.refetch()}
          errorTitle="Couldn't load exceptions"
          isFiltered={filtered}
          renderStackedRow={(item) => <StackedExceptionRow item={item} href={hrefFor(item.id)} closedView={closedView} />}
          noResults={
            <EmptyState
              icon={SearchX}
              title="No exceptions match these filters"
              action={
                <Button type="button" variant="secondary" onClick={() => update({ q: "", severity: [], priority_band: [], status: [], category: [], exception_type: [], assignee: null, due: null })}>
                  Clear filters
                </Button>
              }
            />
          }
          empty={<ViewEmptyState view={params.view} onView={(view) => update({ view })} hasRun={Boolean(lastRun)} />}
        />
        {list.data && total > 0 ? (
          <Pagination
            page={params.page}
            pageSize={params.page_size}
            total={total}
            onPageChange={(page) => update({ page }, "push")}
            onPageSizeChange={(size) => update({ page_size: size as InboxParams["page_size"] })}
          />
        ) : null}
      </section>
    </div>
  );
}

/** Per-view empty copy (S-03 "Empty view"). */
function ViewEmptyState({ view, onView, hasRun }: { view: View; onView: (view: View) => void; hasRun: boolean }) {
  const store = useStore();
  const importsHref = sectionHref(store.id, "imports", store.permissions);
  if (!hasRun && view === "active") {
    return (
      <EmptyState
        icon={Inbox}
        title="No exceptions detected yet"
        description="Exceptions appear after an analysis runs on imported data."
        action={importsHref ? <Link href={importsHref} className="text-link hover:underline">Go to Imports</Link> : undefined}
      />
    );
  }
  const link = (label: string, target: View) => (
    <Button type="button" variant="link" onClick={() => onView(target)}>
      {label}
    </Button>
  );
  switch (view) {
    case "triage":
      return <EmptyState icon={CircleCheck} variant="success" title="Triage queue is clear" description="No open or reopened exceptions." action={link("View all active", "active")} />;
    case "mine":
      return <EmptyState icon={Inbox} title="Nothing is assigned to you" description="Claim an unassigned exception or check with your manager." action={link("View unassigned", "unassigned")} />;
    case "unassigned":
      return <EmptyState icon={CircleCheck} variant="success" title="Every active exception has an owner" />;
    case "closed":
      return <EmptyState icon={Inbox} title="No resolved or dismissed exceptions yet" />;
    default:
      return <EmptyState icon={CircleCheck} variant="success" title="No active exceptions" description="The last analysis found nothing that needs attention." />;
  }
}
