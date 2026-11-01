"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { CircleCheck, Inbox, Rows3, SearchX } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { DataTable } from "@/components/data/data-table";
import { CheckboxGroup, FilterSheet } from "@/components/data/filter-sheet";
import { FilterChips, MultiSelectFilter, Pagination, SearchInput, SelectField, type Chip, type Option } from "@/components/data/list-controls";
import { DateTime } from "@/components/data/values";
import { PageHeader } from "@/components/shell/page-header";
import { sectionHref } from "@/components/shell/nav-config";
import { EmptyState } from "@/components/states/empty-state";
import { PermissionDenied } from "@/components/states/permission-denied";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { exceptionKeys, exceptionsApi } from "@/lib/api/exceptions-api";
import { storeApi, storeKeys } from "@/lib/api/store-api";
import { formatDateTime, formatRelative } from "@/lib/format/datetime";
import { formatCount, formatQuantity } from "@/lib/format/number";
import { useMediaQuery, useStoredBoolean } from "@/lib/hooks/browser";
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
  CLEARED_FILTERS,
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
import { saveQueue } from "./queue";

export const LAST_LIST_KEY = "ro.exceptions.lastList";
export const COMPACT_KEY = "ro.exceptions.compact";
export const LAST_DETECTED_KEY = "ro.exceptions.lastDetectedColumn";

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

/** The filters the sheet edits below 768 px (everything except search, sort and hidden filters). */
type SheetDraft = Pick<InboxParams, "severity" | "priority_band" | "status" | "category" | "exception_type" | "assignee" | "due">;
const EMPTY_DRAFT: SheetDraft = { severity: [], priority_band: [], status: [], category: [], exception_type: [], assignee: null, due: null };

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

/** Row density and the optional Last detected column (S-03 "Density"), remembered per browser. */
function DensityMenu({
  compact,
  onCompact,
  lastDetected,
  onLastDetected,
}: {
  compact: boolean;
  onCompact: (value: boolean) => void;
  lastDetected: boolean;
  onLastDetected: (value: boolean) => void;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button type="button" variant="secondary" size="sm" aria-label={`Density: ${compact ? "compact" : "comfortable"}`}>
          <Rows3 aria-hidden />
          Density
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel>Rows</DropdownMenuLabel>
        <DropdownMenuRadioGroup value={compact ? "compact" : "comfortable"} onValueChange={(value) => onCompact(value === "compact")}>
          <DropdownMenuRadioItem value="comfortable">Comfortable</DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="compact">Compact</DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>
        <DropdownMenuSeparator />
        <DropdownMenuLabel>Columns</DropdownMenuLabel>
        <DropdownMenuCheckboxItem checked={lastDetected} onCheckedChange={(checked) => onLastDetected(checked === true)}>
          Last detected (wide screens)
        </DropdownMenuCheckboxItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/** The work queue (SCREEN_SPECIFICATIONS S-03). */
export function InboxScreen() {
  const store = useStore();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const now = useNow();
  useDocumentTitle("Exceptions");
  const wide = useMediaQuery("(min-width: 768px)");
  const [compact, setCompact] = useStoredBoolean(COMPACT_KEY, false);
  const [lastDetected, setLastDetected] = useStoredBoolean(LAST_DETECTED_KEY, false);
  const [draft, setDraft] = useState<SheetDraft>(EMPTY_DRAFT);

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

  const listHref = `${pathname}?${serializeInboxParams(params).toString()}`;
  // The detail page's breadcrumb returns to the list exactly as the person left it.
  useEffect(() => {
    try {
      window.sessionStorage.setItem(LAST_LIST_KEY, listHref);
    } catch {
      // Storage unavailable: the breadcrumb falls back to the default view.
    }
  }, [listHref]);

  const minute = Math.floor(now.getTime() / 60_000);
  const apiQuery = useMemo(() => toApiQuery(params, new Date(minute * 60_000)), [params, minute]);
  const list = useQuery({
    queryKey: storeKeys.exceptions(store.id, apiQuery),
    queryFn: ({ signal }) => storeApi.exceptions(store.id, apiQuery, signal),
    placeholderData: keepPreviousData,
    refetchInterval: 60_000,
    enabled: canRead && !mineUnavailable,
  });
  // The rows on screen become the queue the investigation page steps through (S-04).
  const rows = list.isPlaceholderData ? undefined : list.data?.items;
  useEffect(() => {
    if (rows) saveQueue({ listHref, items: rows.map((item) => ({ id: item.id, reference: item.reference })) });
  }, [rows, listHref]);

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
  // Evaluation runs are readable with exceptions.read; the chip names the run by its start time.
  const run = useQuery({
    queryKey: ["store", store.id, "evaluations", params.evaluation_run_id],
    queryFn: ({ signal }) => storeApi.evaluation(store.id, params.evaluation_run_id as string, signal),
    enabled: canRead && params.evaluation_run_id !== null,
    staleTime: 5 * 60_000,
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
  const clearAll = () => update(CLEARED_FILTERS);

  const chips: Chip[] = [
    ...(params.evaluation_run_id
      ? [
          {
            key: "run",
            label: run.data
              ? `From evaluation run ${formatDateTime(run.data.started_at, store.timezone, now)}`
              : "From an evaluation run",
            onRemove: () => update({ evaluation_run_id: null }),
          },
        ]
      : []),
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
  const showAssignee = params.view !== "mine" && params.view !== "unassigned";
  const assigneeOptions: Option[] = [
    { value: "", label: "Anyone" },
    ...(canWork ? [{ value: "me", label: "Me" }] : []),
    { value: "unassigned", label: "Unassigned" },
    ...workers.map((member) => ({ value: member.id, label: member.full_name })),
  ];
  const dueOptions: Option[] = [{ value: "", label: "Any time" }, { value: "overdue", label: DUE_LABELS.overdue }, { value: "24h", label: DUE_LABELS["24h"] }];
  const filterOptions = {
    severity: SEVERITIES.map((s) => ({ value: s, label: severityMeta[s].label })),
    priority: BANDS.map((band) => ({ value: band, label: band })),
    status: VIEW_STATUSES[params.view].map((s) => ({ value: s, label: exceptionStatusLabels[s] })),
    category: CATEGORIES.map((c) => ({ value: c, label: categoryLabels[c] })),
    type: TYPES.map((t) => ({ value: t, label: exceptionTypeLabels[t], group: categoryLabels[exceptionTypeCategory[t]] })),
  };
  const sheetCount = [
    params.severity.length,
    params.priority_band.length,
    params.status.length,
    params.category.length,
    params.exception_type.length,
    params.assignee,
    params.due,
  ].filter(Boolean).length;

  const sort = (
    <SelectField label="Sort" value={params.sort} options={SORT_OPTIONS} onChange={(value) => update({ sort: value as InboxParams["sort"] })} />
  );
  const resultCount = (
    <p className="ml-auto text-sm text-muted-foreground" aria-live="polite">
      {list.data ? formatCount(total, "exception") : null}
    </p>
  );

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

      <nav aria-label="Exception views" className="relative -mx-(--page-gutter) overflow-x-auto px-(--page-gutter)">
        <ul className="flex min-w-max gap-1 border-b">
          {views.map((view) => {
            const count = view === "triage" ? triageCount.data : view === "mine" ? mineCount.data : undefined;
            const current = params.view === view;
            return (
              <li key={view}>
                <Link
                  href={`${pathname}?${serializeInboxParams(updateParams(params, { ...CLEARED_FILTERS, view })).toString()}`}
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
          {wide ? (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <SearchInput label="Search exceptions" placeholder="Search reference or title" value={params.q} onChange={(q) => update({ q })} />
                <MultiSelectFilter
                  label="Severity"
                  options={filterOptions.severity}
                  selected={params.severity}
                  onChange={(values) => update({ severity: values as InboxParams["severity"] })}
                />
                <MultiSelectFilter
                  label="Priority"
                  options={filterOptions.priority}
                  selected={params.priority_band}
                  onChange={(values) => update({ priority_band: values as InboxParams["priority_band"] })}
                />
                <MultiSelectFilter
                  label="Status"
                  options={filterOptions.status}
                  selected={params.status}
                  onChange={(values) => update({ status: values as InboxParams["status"] })}
                />
                <MultiSelectFilter
                  label="Category"
                  options={filterOptions.category}
                  selected={params.category}
                  onChange={(values) => update({ category: values as InboxParams["category"] })}
                />
                <MultiSelectFilter
                  label="Type"
                  options={filterOptions.type}
                  selected={params.exception_type}
                  onChange={(values) => update({ exception_type: values as InboxParams["exception_type"] })}
                />
              </div>
              <div className="flex flex-wrap items-center gap-3">
                {showAssignee ? (
                  <SelectField label="Assignee" value={params.assignee ?? ""} options={assigneeOptions} onChange={(value) => update({ assignee: value || null })} />
                ) : null}
                {!closedView ? (
                  <SelectField label="Due" value={params.due ?? ""} options={dueOptions} onChange={(value) => update({ due: (value || null) as InboxParams["due"] })} />
                ) : null}
                {sort}
                <DensityMenu compact={compact} onCompact={setCompact} lastDetected={lastDetected} onLastDetected={setLastDetected} />
                {resultCount}
              </div>
            </>
          ) : (
            <>
              <SearchInput label="Search exceptions" placeholder="Search reference or title" value={params.q} onChange={(q) => update({ q })} />
              <div className="flex flex-wrap items-center gap-3">
                <FilterSheet
                  count={sheetCount}
                  onOpen={() =>
                    setDraft({
                      severity: params.severity,
                      priority_band: params.priority_band,
                      status: params.status,
                      category: params.category,
                      exception_type: params.exception_type,
                      assignee: params.assignee,
                      due: params.due,
                    })
                  }
                  onApply={() => update(draft)}
                  onReset={() => setDraft(EMPTY_DRAFT)}
                >
                  <CheckboxGroup
                    legend="Severity"
                    options={filterOptions.severity}
                    selected={draft.severity}
                    onChange={(values) => setDraft({ ...draft, severity: values as InboxParams["severity"] })}
                  />
                  <CheckboxGroup
                    legend="Priority"
                    options={filterOptions.priority}
                    selected={draft.priority_band}
                    onChange={(values) => setDraft({ ...draft, priority_band: values as InboxParams["priority_band"] })}
                  />
                  <CheckboxGroup
                    legend="Status"
                    options={filterOptions.status}
                    selected={draft.status}
                    onChange={(values) => setDraft({ ...draft, status: values as InboxParams["status"] })}
                  />
                  <CheckboxGroup
                    legend="Category"
                    options={filterOptions.category}
                    selected={draft.category}
                    onChange={(values) => setDraft({ ...draft, category: values as InboxParams["category"] })}
                  />
                  <CheckboxGroup
                    legend="Type"
                    options={filterOptions.type}
                    selected={draft.exception_type}
                    onChange={(values) => setDraft({ ...draft, exception_type: values as InboxParams["exception_type"] })}
                  />
                  {showAssignee ? (
                    <SelectField label="Assignee" value={draft.assignee ?? ""} options={assigneeOptions} onChange={(value) => setDraft({ ...draft, assignee: value || null })} />
                  ) : null}
                  {!closedView ? (
                    <SelectField
                      label="Due"
                      value={draft.due ?? ""}
                      options={dueOptions}
                      onChange={(value) => setDraft({ ...draft, due: (value || null) as InboxParams["due"] })}
                    />
                  ) : null}
                </FilterSheet>
                {sort}
                {resultCount}
              </div>
            </>
          )}
          <FilterChips chips={chips} onClearAll={clearAll} />
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
          columns={exceptionColumns((item) => hrefFor(item.id), closedView, { lastDetected })}
          rows={list.data?.items}
          getRowId={(item) => item.id}
          status={list.isPending ? "loading" : list.isError ? "error" : "success"}
          isFetching={list.isPlaceholderData}
          error={list.error}
          onRetry={() => void list.refetch()}
          errorTitle="Couldn't load exceptions"
          isFiltered={filtered}
          density={compact ? "compact" : "comfortable"}
          renderStackedRow={(item) => <StackedExceptionRow item={item} href={hrefFor(item.id)} closedView={closedView} />}
          noResults={
            <EmptyState
              icon={SearchX}
              title="No exceptions match these filters"
              action={
                <Button type="button" variant="secondary" onClick={clearAll}>
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
