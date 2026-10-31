"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { CircleCheck, Download, SearchX } from "lucide-react";
import { useState } from "react";

import { DataTable, type Column } from "@/components/data/data-table";
import { Pagination, SelectField } from "@/components/data/list-controls";
import { Section } from "@/components/data/section";
import { NoValue } from "@/components/data/values";
import { EmptyState } from "@/components/states/empty-state";
import { StatusPill } from "@/components/status/status-pill";
import { Button } from "@/components/ui/button";
import { importKeys, importsApi, type ImportDetail, type ImportIssue } from "@/lib/api/imports-api";
import { formatCount, formatQuantity } from "@/lib/format/number";
import { importIssueMeta } from "@/lib/status-maps";
import { useStore } from "@/lib/store/store-context";
import { cn } from "@/lib/utils";

import { useDownload } from "./import-actions";

type Severity = "ALL" | "ERROR" | "WARNING";
const PAGE_SIZE = 25;

/** Issue counts per severity, from the summary's per-code counts and the code catalogue. */
export function issueCounts(record: ImportDetail) {
  const byCode = record.summary.issue_counts_by_code ?? {};
  let errors = 0;
  let warnings = 0;
  let all = 0;
  for (const [code, count] of Object.entries(byCode)) {
    all += count;
    const level = importIssueMeta[code]?.level;
    if (level === "WARNING") warnings += count;
    else if (level === "ERROR") errors += count;
  }
  return { all, errors, warnings };
}

function SeverityTag({ severity }: { severity: ImportIssue["severity"] }) {
  return severity === "ERROR" ? <StatusPill tone="danger" label="Error" /> : <StatusPill tone="warning" label="Warning" />;
}

/**
 * Every issue of an import (COMPONENT_INVENTORY IssueTable): severity tabs, a code filter and
 * server pagination, with the API message and the catalogue's fix text side by side.
 */
export function IssueTable({ record, emptyText }: { record: ImportDetail; emptyText: string }) {
  const store = useStore();
  const [severity, setSeverity] = useState<Severity>("ALL");
  const [code, setCode] = useState("");
  const [page, setPage] = useState(1);
  const { pending, run } = useDownload();
  const counts = issueCounts(record);

  const query = { severity: severity === "ALL" ? undefined : severity, code: code || undefined, page, page_size: PAGE_SIZE };
  const issues = useQuery({
    queryKey: importKeys.issues(store.id, record.id, query),
    queryFn: ({ signal }) => importsApi.issues(store.id, record.id, query, signal),
    placeholderData: keepPreviousData,
    enabled: counts.all > 0,
  });

  const codes = Object.keys(record.summary.issue_counts_by_code ?? {})
    .filter((item) => severity === "ALL" || importIssueMeta[item]?.level === severity)
    .sort();
  const tabs: Array<{ value: Severity; label: string; count: number }> = [
    { value: "ALL", label: "All", count: counts.all },
    { value: "ERROR", label: "Errors", count: counts.errors },
    { value: "WARNING", label: "Warnings", count: counts.warnings },
  ];
  const filter = (next: { severity?: Severity; code?: string }) => {
    if (next.severity !== undefined) {
      setSeverity(next.severity);
      setCode("");
    }
    if (next.code !== undefined) setCode(next.code);
    setPage(1);
  };

  const columns: Column<ImportIssue>[] = [
    { id: "row", header: "Row", align: "right", pinned: true, cell: (issue) => (issue.row_number === null ? "File" : formatQuantity(issue.row_number)) },
    { id: "column", header: "Column", cell: (issue) => (issue.column ? <span className="font-mono text-mono">{issue.column}</span> : <NoValue />) },
    { id: "code", header: "Code", hideBelow: "md", cell: (issue) => <span className="font-mono text-xs whitespace-nowrap">{issue.code}</span> },
    { id: "severity", header: "Severity", cell: (issue) => <SeverityTag severity={issue.severity} /> },
    {
      id: "message",
      header: "Message",
      cell: (issue) => (
        <div className="flex min-w-56 flex-col gap-0.5">
          <span>{issue.message}</span>
          {importIssueMeta[issue.code] ? <span className="text-xs text-muted-foreground">{importIssueMeta[issue.code].fix}</span> : null}
        </div>
      ),
    },
    {
      id: "value",
      header: "Value",
      hideBelow: "lg",
      cell: (issue) => (issue.raw_value ? <span className="font-mono text-xs break-all">{issue.raw_value}</span> : <NoValue />),
    },
  ];

  const download =
    counts.all > 0 ? (
      <Button
        type="button"
        variant="secondary"
        size="sm"
        pending={pending !== null}
        onClick={() =>
          void run("issues", importsApi.issuesCsvPath(store.id, record.id), `import-${record.id}-issues.csv`, "Couldn't download the issues CSV.")
        }
      >
        <Download aria-hidden />
        Download issues CSV
      </Button>
    ) : undefined;

  return (
    <Section id="issues" title="Issues" aside={download}>
      {counts.all === 0 ? (
        <EmptyState icon={CircleCheck} variant="success" title={emptyText} />
      ) : (
        <div className="-mx-4 flex flex-col md:-mx-5">
          <div className="flex flex-wrap items-center gap-3 border-b px-4 pb-3 md:px-5">
            <div role="group" aria-label="Severity" className="flex gap-1 rounded-md bg-muted p-0.5">
              {tabs.map((tab) => (
                <button
                  key={tab.value}
                  type="button"
                  aria-pressed={severity === tab.value}
                  onClick={() => filter({ severity: tab.value })}
                  className={cn(
                    "rounded-sm px-2.5 py-1 text-sm text-muted-foreground transition-colors",
                    severity === tab.value && "bg-card font-medium text-foreground shadow-xs",
                  )}
                >
                  {tab.label} <span className="tabular-nums">{formatQuantity(tab.count)}</span>
                </button>
              ))}
            </div>
            <SelectField
              label="Code"
              value={code}
              options={[{ value: "", label: "Any" }, ...codes.map((item) => ({ value: item, label: item }))]}
              onChange={(value) => filter({ code: value })}
            />
            <p className="ml-auto text-sm text-muted-foreground" aria-live="polite">
              {issues.data ? formatCount(issues.data.total, "issue") : null}
            </p>
          </div>
          <DataTable
            caption={`Issues, page ${page}, by row number`}
            columns={columns}
            rows={issues.data?.items}
            getRowId={(issue) => issue.id}
            status={issues.isPending ? "loading" : issues.isError ? "error" : "success"}
            isFetching={issues.isPlaceholderData}
            error={issues.error}
            onRetry={() => void issues.refetch()}
            errorTitle="Couldn't load the issues"
            isFiltered={severity !== "ALL" || code !== ""}
            density="compact"
            noResults={<EmptyState icon={SearchX} title="No issues match these filters" />}
            empty={<EmptyState icon={CircleCheck} variant="success" title={emptyText} />}
          />
          {issues.data && issues.data.total > PAGE_SIZE ? (
            <Pagination page={page} pageSize={PAGE_SIZE} total={issues.data.total} onPageChange={setPage} />
          ) : null}
        </div>
      )}
    </Section>
  );
}
