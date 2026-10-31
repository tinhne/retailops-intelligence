"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { FileUp, SearchX } from "lucide-react";
import Link from "next/link";

import { DataTable, type Column } from "@/components/data/data-table";
import { FilterChips, MultiSelectFilter, Pagination, SelectField, type Chip } from "@/components/data/list-controls";
import { NoValue } from "@/components/data/values";
import { PageHeader } from "@/components/shell/page-header";
import { EmptyState } from "@/components/states/empty-state";
import { PermissionDenied } from "@/components/states/permission-denied";
import { ImportStatusPill } from "@/components/status/status-pill";
import { Button } from "@/components/ui/button";
import { exceptionKeys, exceptionsApi } from "@/lib/api/exceptions-api";
import { importKeys, importsApi, type ImportItem } from "@/lib/api/imports-api";
import { formatDateTimeShort, zoneGenericName } from "@/lib/format/datetime";
import { formatCount, formatQuantity } from "@/lib/format/number";
import { useDocumentTitle } from "@/lib/hooks/use-document-title";
import { useListState } from "@/lib/hooks/use-list-state";
import { useNow } from "@/lib/hooks/use-now";
import { defineListParams } from "@/lib/list-params";
import { IMPORT_TYPES_IN_ORDER, importModeLabels, importStatusMeta, importTypeLabels, type ImportStatus, type ImportType } from "@/lib/status-maps";
import { useStore } from "@/lib/store/store-context";
import { cn } from "@/lib/utils";

import { NewImportButton, TemplateMenu } from "./import-actions";
import { IN_FLIGHT, POLL_MS } from "./shared";

const STATUSES: ImportStatus[] = ["VALIDATED", "REJECTED", "COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED", "DISCARDED", "APPLYING", "UPLOADED", "VALIDATING"];

export const importsList = defineListParams(
  {
    import_type: { kind: "one", values: IMPORT_TYPES_IN_ORDER },
    status: { kind: "many", values: STATUSES },
  },
  { sorts: ["-created_at"], defaultSort: "-created_at", pageSizes: [25, 50, 100], defaultPageSize: 25 },
);

/** Applied imports report what was applied; the rest report the preview's expectations. */
export function changeCounts(item: ImportItem) {
  const applied = item.summary.applied;
  return applied ? { creates: applied.creates, updates: applied.updates } : { creates: item.summary.creates, updates: item.summary.updates };
}

/** Import history and the way into new imports (SCREEN_SPECIFICATIONS S-11). */
export function ImportsScreen() {
  const store = useStore();
  const now = useNow();
  useDocumentTitle("Imports");
  const canRead = store.permissions.has("imports.read");
  const { params, update, clearAll, isFiltered } = useListState(importsList);
  const zone = zoneGenericName(store.timezone);

  const query = {
    import_type: params.import_type ?? undefined,
    status: params.status,
    sort: params.sort,
    page: params.page,
    page_size: params.page_size,
  };
  const list = useQuery({
    queryKey: importKeys.list(store.id, query),
    queryFn: ({ signal }) => importsApi.list(store.id, query, signal),
    placeholderData: keepPreviousData,
    enabled: canRead,
    refetchInterval: (q) => (q.state.data?.items.some((item) => IN_FLIGHT.includes(item.status)) ? POLL_MS : false),
  });
  const members = useQuery({
    queryKey: exceptionKeys.members(store.id),
    queryFn: ({ signal }) => exceptionsApi.members(store.id, signal),
    enabled: canRead && store.permissions.has("exceptions.read"),
    staleTime: 5 * 60_000,
  });

  if (!canRead) return <PermissionDenied pageName="imports" permission="imports.read" />;

  const uploader = (id: string | null) =>
    id === null ? "System" : members.data ? (members.data.items.find((member) => member.id === id)?.full_name ?? "Former member") : null;
  const hrefFor = (item: ImportItem) => `/s/${store.id}/imports/${item.id}`;
  const chips: Chip[] = [
    ...(params.import_type
      ? [{ key: "type", label: `Type: ${importTypeLabels[params.import_type as ImportType]}`, onRemove: () => update({ import_type: null }) }]
      : []),
    ...(params.status.length
      ? [
          {
            key: "status",
            label: `Status: ${params.status.map((status) => importStatusMeta[status as ImportStatus].label).join(", ")}`,
            onRemove: () => update({ status: [] }),
          },
        ]
      : []),
  ];

  const fileLink = (item: ImportItem) => (
    <Link href={hrefFor(item)} className="inline-block min-w-44 font-mono text-mono break-words outline-offset-[-2px] after:absolute after:inset-0 hover:underline">
      {item.original_filename}
    </Link>
  );
  const uploaded = (item: ImportItem) => (
    <time dateTime={item.created_at} className="whitespace-nowrap">
      {formatDateTimeShort(item.created_at, store.timezone, now)}
    </time>
  );
  const columns: Column<ImportItem>[] = [
    { id: "file", header: "File", cell: fileLink },
    { id: "type", header: "Type", hideBelow: "md", cell: (item) => <span className="whitespace-nowrap">{importTypeLabels[item.import_type]}</span> },
    { id: "status", header: "Status", cell: (item) => <ImportStatusPill status={item.status} /> },
    { id: "mode", header: "Mode", hideBelow: "2xl", cell: (item) => (item.mode ? <span className="whitespace-nowrap">{importModeLabels[item.mode]}</span> : <NoValue />) },
    { id: "rows", header: "Rows", align: "right", hideBelow: "md", cell: (item) => formatQuantity(item.summary.rows_total) },
    {
      id: "changes",
      header: "Create · Update",
      align: "right",
      hideBelow: "lg",
      cell: (item) => {
        if (item.status === "REJECTED") return <NoValue />;
        const counts = changeCounts(item);
        return `${formatQuantity(counts.creates)} · ${formatQuantity(counts.updates)}`;
      },
    },
    {
      id: "errors",
      header: "Rows with errors",
      align: "right",
      hideBelow: "md",
      cell: (item) => <span className={cn(item.summary.rows_with_errors > 0 && "text-tone-danger-fg")}>{formatQuantity(item.summary.rows_with_errors)}</span>,
    },
    { id: "warnings", header: "Rows with warnings", align: "right", hideBelow: "2xl", cell: (item) => formatQuantity(item.summary.rows_with_warnings) },
    { id: "by", header: "Uploaded by", hideBelow: "lg", cell: (item) => <span className="whitespace-nowrap">{uploader(item.created_by) ?? <NoValue />}</span> },
    { id: "uploaded", header: `Uploaded (${zone})`, cell: uploaded },
  ];

  const total = list.data?.total ?? 0;
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Imports"
        subtitle="Recommended order: products → inventory adjustments → orders → order items. Each file references the ones before it."
        actions={
          <>
            <TemplateMenu />
            <NewImportButton />
          </>
        }
      />
      <section aria-label="Import history" className="rounded-lg border bg-card">
        <div className="flex flex-col gap-3 border-b p-4">
          <div className="flex flex-wrap items-center gap-3">
            <SelectField
              label="Type"
              value={params.import_type ?? ""}
              options={[{ value: "", label: "Any" }, ...IMPORT_TYPES_IN_ORDER.map((type) => ({ value: type, label: importTypeLabels[type] }))]}
              onChange={(value) => update({ import_type: value || null })}
            />
            <MultiSelectFilter
              label="Status"
              options={STATUSES.slice(0, 7).map((status) => ({ value: status, label: importStatusMeta[status].label }))}
              selected={params.status}
              onChange={(status) => update({ status })}
            />
            <p className="ml-auto text-sm text-muted-foreground" aria-live="polite">
              {list.data ? formatCount(total, "import") : null}
            </p>
          </div>
          <FilterChips chips={chips} onClearAll={clearAll} />
        </div>
        <DataTable
          caption={`Imports, page ${params.page}, newest first`}
          columns={columns}
          rows={list.data?.items}
          getRowId={(item) => item.id}
          status={list.isPending ? "loading" : list.isError ? "error" : "success"}
          isFetching={list.isPlaceholderData}
          error={list.error}
          onRetry={() => void list.refetch()}
          errorTitle="Couldn't load imports"
          isFiltered={isFiltered}
          renderStackedRow={(item) => (
            <div className="flex flex-col gap-1 p-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                {fileLink(item)}
                <ImportStatusPill status={item.status} />
              </div>
              <p className="text-sm text-muted-foreground">
                {importTypeLabels[item.import_type]} · {formatCount(item.summary.rows_total, "row")} ·{" "}
                <span className={cn(item.summary.rows_with_errors > 0 && "text-tone-danger-fg")}>
                  {formatQuantity(item.summary.rows_with_errors)} with errors
                </span>
              </p>
              <p className="text-sm text-muted-foreground">
                {uploaded(item)}
                {uploader(item.created_by) ? ` · ${uploader(item.created_by)}` : ""}
              </p>
            </div>
          )}
          noResults={
            <EmptyState
              icon={SearchX}
              title="No imports match these filters"
              action={
                <Button type="button" variant="secondary" onClick={clearAll}>
                  Clear filters
                </Button>
              }
            />
          }
          empty={
            <EmptyState
              icon={FileUp}
              title="No imports yet"
              description="Start with products, then inventory adjustments, orders and order items. Each file type has a template."
              action={
                <div className="flex flex-wrap justify-center gap-2">
                  <NewImportButton />
                  <TemplateMenu />
                </div>
              }
            />
          }
        />
        {list.data && total > 0 ? (
          <Pagination page={params.page} pageSize={params.page_size} total={total} onPageChange={(page) => update({ page }, "push")} onPageSizeChange={(page_size) => update({ page_size })} />
        ) : null}
      </section>
    </div>
  );
}
