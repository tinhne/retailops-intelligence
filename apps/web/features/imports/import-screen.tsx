"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ChevronRight, CircleAlert, CircleCheck, CircleSlash, Info, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { ActionButton } from "@/components/actions/action-button";
import { Section, StatTile } from "@/components/data/section";
import { DateTime, NoValue } from "@/components/data/values";
import { sectionHref } from "@/components/shell/nav-config";
import { CopyButton } from "@/components/states/copy-button";
import { ErrorState } from "@/components/states/error-state";
import { NotFoundState } from "@/components/states/not-found-state";
import { PermissionDenied } from "@/components/states/permission-denied";
import { ImportStatusPill } from "@/components/status/status-pill";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { exceptionKeys, exceptionsApi } from "@/lib/api/exceptions-api";
import { isApiError, userMessage } from "@/lib/api/errors";
import { importKeys, importsApi, type ImportDetail, type PreviewRow } from "@/lib/api/imports-api";
import { storeApi } from "@/lib/api/store-api";
import { formatQuantity } from "@/lib/format/number";
import { useDocumentTitle } from "@/lib/hooks/use-document-title";
import { useNow } from "@/lib/hooks/use-now";
import { importIssueMeta, importModeLabels, importTypeLabels, rowActionLabels, type RowAction } from "@/lib/status-maps";
import { usePermission, useStore } from "@/lib/store/store-context";
import { cn } from "@/lib/utils";

import { ApplyStep } from "./apply-step";
import { IMPORT_TYPE_INFO } from "./contracts";
import { newImportHref } from "./import-actions";
import { IssueTable } from "./issue-table";
import { formatFileSize, IN_FLIGHT, POLL_MS } from "./shared";

const STEPS = ["Upload", "Preview", "Apply", "Summary"] as const;

/** "23h 58m" until the preview expires. */
export function expiresIn(expiresAt: string, now: Date): string {
  const minutes = Math.max(0, Math.floor((new Date(expiresAt).getTime() - now.getTime()) / 60_000));
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}

/** Discarded by expiry when the record changed at or after its expiry time (the API sets no actor). */
export const expiredAutomatically = (record: ImportDetail) =>
  record.expires_at !== null && new Date(record.updated_at).getTime() >= new Date(record.expires_at).getTime();

function Stepper({ current }: { current: number }) {
  return (
    <>
      <p className="text-sm text-muted-foreground md:hidden">
        Step {current + 1} of {STEPS.length} · {STEPS[current]}
      </p>
      <ol aria-label="Import steps" className="hidden items-center gap-2 md:flex">
        {STEPS.map((step, index) => (
          <li key={step} aria-current={index === current ? "step" : undefined} className="flex items-center gap-2">
            {index > 0 ? <span aria-hidden className="h-px w-10 bg-border" /> : null}
            <span
              className={cn(
                "flex size-6 items-center justify-center rounded-full border text-xs tabular-nums",
                index < current && "border-primary bg-primary text-primary-foreground",
                index === current && "border-primary text-primary",
              )}
            >
              {index < current ? <Check aria-hidden className="size-3.5" /> : index + 1}
            </span>
            <span className={cn("text-sm", index === current ? "font-medium" : "text-muted-foreground")}>
              {step}
              {index < current ? <span className="sr-only"> (completed)</span> : null}
            </span>
          </li>
        ))}
      </ol>
    </>
  );
}

function PreviewTiles({ record }: { record: ImportDetail }) {
  const { summary } = record;
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
      <StatTile label="Rows">{formatQuantity(summary.rows_total)}</StatTile>
      <StatTile label="Create">{formatQuantity(summary.creates)}</StatTile>
      <StatTile label="Update">{formatQuantity(summary.updates)}</StatTile>
      <StatTile label="Unchanged">{formatQuantity(summary.unchanged)}</StatTile>
      <StatTile label="Rows with errors">
        <span className={cn(summary.rows_with_errors > 0 && "text-tone-danger-fg")}>{formatQuantity(summary.rows_with_errors)}</span>
      </StatTile>
      <StatTile label="Rows with warnings">{formatQuantity(summary.rows_with_warnings)}</StatTile>
    </div>
  );
}

function AppliedTiles({ record }: { record: ImportDetail }) {
  const applied = record.summary.applied;
  if (!applied) return null;
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
      <StatTile label="Mode">{importModeLabels[applied.mode]}</StatTile>
      <StatTile label="Created">{formatQuantity(applied.creates)}</StatTile>
      <StatTile label="Updated">{formatQuantity(applied.updates)}</StatTile>
      <StatTile label="Unchanged">{formatQuantity(applied.unchanged)}</StatTile>
      <StatTile label="Skipped">
        <span className={cn(applied.skipped > 0 && "text-tone-warning-fg")}>{formatQuantity(applied.skipped)}</span>
      </StatTile>
    </div>
  );
}

/** File-level warnings and the counted warnings worth a callout before applying (S-12 step 2). */
function WarningCallouts({ record }: { record: ImportDetail }) {
  const store = useStore();
  const counts = record.summary.issue_counts_by_code ?? {};
  const notes = [
    ...record.file_issues.filter((issue) => issue.severity === "WARNING").map((issue) => ({ key: issue.id, text: issue.message, code: issue.code })),
    ...(counts.TIMEZONE_ASSUMED
      ? [
          {
            key: "tz",
            code: "TIMEZONE_ASSUMED",
            text: `${formatQuantity(counts.TIMEZONE_ASSUMED)} ${counts.TIMEZONE_ASSUMED === 1 ? "timestamp had" : "timestamps had"} no UTC offset and ${counts.TIMEZONE_ASSUMED === 1 ? "was" : "were"} read as store time, ${store.timezone}.`,
          },
        ]
      : []),
    ...(counts.ALREADY_APPLIED
      ? [
          {
            key: "applied",
            code: "ALREADY_APPLIED",
            text: `${formatQuantity(counts.ALREADY_APPLIED)} ${counts.ALREADY_APPLIED === 1 ? "reference was" : "references were"} already applied and will have no effect.`,
          },
        ]
      : []),
  ];
  if (notes.length === 0) return null;
  return (
    <div className="flex flex-col gap-2">
      {notes.map((note) => (
        <Alert key={note.key} tone="warning">
          <TriangleAlert aria-hidden />
          <AlertDescription>
            <p>
              {note.text} <span className="font-mono text-xs">({note.code})</span>
            </p>
            {importIssueMeta[note.code] ? <p className="text-sm">{importIssueMeta[note.code].fix}</p> : null}
          </AlertDescription>
        </Alert>
      ))}
    </div>
  );
}

/** The API lists rows that create, update or fail (never unchanged ones), up to 50. */
function ExpectedChanges({ rows, listed }: { rows: PreviewRow[]; listed: number }) {
  const [action, setAction] = useState<RowAction | "">("");
  const shown = action ? rows.filter((row) => row.action === action) : rows;
  const actions = (Object.keys(rowActionLabels) as RowAction[]).filter((item) => rows.some((row) => row.action === item));
  return (
    <Section
      id="changes"
      title={rows.length < listed ? `Expected changes (first ${formatQuantity(rows.length)} of ${formatQuantity(listed)})` : "Expected changes"}
      aside={
        actions.length > 1 ? (
          <div role="group" aria-label="Filter by action" className="flex flex-wrap gap-1">
            {(["", ...actions] as Array<RowAction | "">).map((item) => (
              <Button key={item || "all"} type="button" size="sm" variant="ghost" aria-pressed={action === item} onClick={() => setAction(item)} className={cn(action === item && "bg-surface-selected")}>
                {item ? rowActionLabels[item] : "All"}
              </Button>
            ))}
          </div>
        ) : undefined
      }
    >
      <p className="mb-3 text-sm text-muted-foreground">Rows that create, update or have errors. Unchanged rows are not listed.</p>
      {rows.length === 0 ? (
        <p className="text-body text-muted-foreground">No row changes anything.</p>
      ) : (
        <div className="relative -mx-4 overflow-x-auto md:-mx-5">
          <table className="w-full text-sm">
            <caption className="sr-only">Expected change per row</caption>
            <thead className="bg-surface-subtle text-xs text-muted-foreground">
              <tr>
                <th scope="col" className="sticky left-0 bg-surface-subtle px-4 py-2 text-right font-medium md:pl-5">Row</th>
                <th scope="col" className="px-3 py-2 text-left font-medium">Key</th>
                <th scope="col" className="px-3 py-2 text-left font-medium">Action</th>
                <th scope="col" className="px-4 py-2 text-left font-medium md:pr-5">Changed fields</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((row) => (
                <tr key={row.row_number} className="border-t">
                  <td className="sticky left-0 bg-card px-4 py-2 text-right tabular-nums md:pl-5">{formatQuantity(row.row_number)}</td>
                  <td className="px-3 py-2 font-mono text-mono whitespace-nowrap">{row.key}</td>
                  <td className={cn("px-3 py-2 whitespace-nowrap", row.action === "SKIP" && "text-tone-danger-fg")}>
                    {row.action === "SKIP" ? <CircleAlert aria-hidden className="mr-1 inline size-3.5" /> : null}
                    {rowActionLabels[row.action]}
                  </td>
                  <td className="px-4 py-2 md:pr-5">{row.changed_fields.length ? row.changed_fields.join(", ") : <NoValue />}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  );
}

function DiscardDialog({ record, open, onOpenChange }: { record: ImportDetail; open: boolean; onOpenChange: (open: boolean) => void }) {
  const store = useStore();
  const queryClient = useQueryClient();
  const discard = useMutation({
    mutationFn: () => importsApi.discard(store.id, record.id),
    onSuccess: (updated) => {
      queryClient.setQueryData(importKeys.detail(store.id, record.id), updated);
      void queryClient.invalidateQueries({ queryKey: importKeys.all(store.id) });
      toast.success("Import discarded");
      onOpenChange(false);
    },
  });
  return (
    <Dialog open={open} onOpenChange={(next) => !discard.isPending && onOpenChange(next)}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Discard this import?</DialogTitle>
          <DialogDescription>The file is deleted and no data changes. The issue list stays available for reference.</DialogDescription>
        </DialogHeader>
        {discard.isError ? (
          <Alert tone="danger" role="alert">
            <CircleAlert aria-hidden />
            <AlertDescription>
              <p>{userMessage(discard.error)}</p>
            </AlertDescription>
          </Alert>
        ) : null}
        <DialogFooter>
          <Button type="button" variant="secondary" onClick={() => onOpenChange(false)} disabled={discard.isPending}>
            Cancel
          </Button>
          <Button type="button" variant="destructive" pending={discard.isPending} onClick={() => discard.mutate()}>
            Discard import
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** The analysis the apply triggered (S-12 step 4, S-13 §5). */
function EvaluationPanel({ record }: { record: ImportDetail }) {
  const store = useStore();
  const runId = record.evaluation_run_id;
  const run = useQuery({
    queryKey: ["store", store.id, "evaluations", runId],
    queryFn: ({ signal }) => storeApi.evaluation(store.id, runId as string, signal),
    enabled: runId !== null,
    refetchInterval: (q) => (q.state.data?.status === "RUNNING" ? POLL_MS : false),
  });
  const exceptionsHref = sectionHref(store.id, "exceptions", store.permissions, { view: "triage" });
  const skipped = "Another analysis was running, so this import's analysis was skipped. The next scheduled run, within 15 minutes, will evaluate the new data.";
  const failed = "The import is complete, but its analysis failed. No exceptions were changed by it, and the next scheduled run will catch up.";

  let body: React.ReactNode;
  if (record.summary.evaluation_error || run.data?.status === "FAILED") {
    body = (
      <Alert tone="warning">
        <TriangleAlert aria-hidden />
        <AlertDescription>
          <p>{failed}</p>
        </AlertDescription>
      </Alert>
    );
  } else if (runId === null || run.data?.status === "SKIPPED") {
    body = (
      <Alert tone="info">
        <Info aria-hidden />
        <AlertDescription>
          <p>{skipped}</p>
        </AlertDescription>
      </Alert>
    );
  } else if (run.isPending) {
    body = <Skeleton className="h-6 w-80" />;
  } else if (run.isError) {
    body = <ErrorState title="Couldn't load the analysis" error={run.error} onRetry={() => void run.refetch()} />;
  } else if (run.data.status === "RUNNING") {
    body = <p className="text-body text-muted-foreground">The analysis is running…</p>;
  } else {
    const n = (key: string) => formatQuantity(run.data.counts[key] ?? 0);
    body = (
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-body">
          {n("created")} new exceptions · {n("refreshed")} refreshed · {n("resolved")} resolved · {n("reopened")} reopened
        </p>
        {exceptionsHref && (run.data.counts.created ?? 0) > 0 ? (
          <Link href={exceptionsHref} className="text-sm text-link hover:underline">
            View exceptions to triage
          </Link>
        ) : null}
      </div>
    );
  }
  return (
    <Section id="evaluation" title="Analysis after import">
      {body}
    </Section>
  );
}

/** Upload, validation and apply facts (S-13 §3). */
function Details({ record }: { record: ImportDetail }) {
  const store = useStore();
  const members = useQuery({
    queryKey: exceptionKeys.members(store.id),
    queryFn: ({ signal }) => exceptionsApi.members(store.id, signal),
    enabled: store.permissions.has("exceptions.read"),
    staleTime: 5 * 60_000,
  });
  const person = (id: string | null) =>
    id === null ? null : (members.data?.items.find((member) => member.id === id)?.full_name ?? (members.data ? "Former member" : null));
  const when = (at: string | null, by: string | null) =>
    at ? (
      <>
        <DateTime value={at} />
        {person(by) ? ` · ${person(by)}` : ""}
      </>
    ) : (
      <NoValue />
    );
  return (
    <Section id="details" title="Details">
      <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-1.5 text-body">
        <dt className="text-muted-foreground">Type</dt>
        <dd>{importTypeLabels[record.import_type]}</dd>
        <dt className="text-muted-foreground">Mode</dt>
        <dd>{record.mode ? importModeLabels[record.mode] : <NoValue />}</dd>
        <dt className="text-muted-foreground">Uploaded</dt>
        <dd>{when(record.created_at, record.created_by)}</dd>
        <dt className="text-muted-foreground">Validated</dt>
        <dd>{when(record.validated_at, null)}</dd>
        <dt className="text-muted-foreground">Applied</dt>
        <dd>{when(record.applied_at, record.applied_by)}</dd>
        <dt className="text-muted-foreground">Size</dt>
        <dd>{formatFileSize(record.size_bytes)}</dd>
        <dt className="text-muted-foreground">Rows</dt>
        <dd className="tabular-nums">{record.row_count === null ? <NoValue /> : formatQuantity(record.row_count)}</dd>
        <dt className="text-muted-foreground">SHA-256</dt>
        <dd className="flex items-center gap-1">
          <span className="font-mono text-mono" title={record.file_sha256}>
            {record.file_sha256.slice(0, 12)}
          </span>
          <CopyButton value={record.file_sha256} label="Copy SHA-256" />
        </dd>
      </dl>
    </Section>
  );
}

/** The outcome banner and callouts for imports that are no longer in progress (S-12 step 4, S-13 §2). */
function Outcome({ record }: { record: ImportDetail }) {
  const store = useStore();
  const again = newImportHref(store, record.import_type);
  const uploadAgain = again ? (
    <Link href={again} className="text-link hover:underline">
      Upload a corrected file
    </Link>
  ) : null;
  const applied = record.summary.applied;
  const appliedRows = applied ? applied.creates + applied.updates + applied.unchanged : 0;

  switch (record.status) {
    case "COMPLETED":
      return (
        <Alert tone="success">
          <CircleCheck aria-hidden />
          <AlertDescription>
            <p>Import completed. {formatQuantity(appliedRows)} rows applied.</p>
          </AlertDescription>
        </Alert>
      );
    case "COMPLETED_WITH_ERRORS":
      return (
        <Alert tone="warning">
          <TriangleAlert aria-hidden />
          <AlertDescription>
            <p>
              Import completed. {formatQuantity(appliedRows)} rows applied, {formatQuantity(applied?.skipped ?? 0)} skipped with your confirmation.
              They are listed below and in the issues CSV.
            </p>
          </AlertDescription>
        </Alert>
      );
    case "REJECTED":
      return (
        <div className="flex flex-col gap-2">
          {record.file_issues
            .filter((issue) => issue.severity === "ERROR")
            .map((issue) => (
              <Alert key={issue.id} tone="danger">
                <CircleAlert aria-hidden />
                <AlertDescription>
                  <p>
                    <span className="font-mono text-xs">{issue.code}</span> {issue.message}
                  </p>
                  {importIssueMeta[issue.code] ? <p className="text-sm">How to fix: {importIssueMeta[issue.code].fix}</p> : null}
                  {uploadAgain}
                </AlertDescription>
              </Alert>
            ))}
        </div>
      );
    case "FAILED":
      return (
        <Alert tone="danger">
          <CircleAlert aria-hidden />
          <AlertDescription>
            <p>Apply failed and was rolled back. No data was changed.</p>
            {record.failure_reason ? <p className="text-sm">{record.failure_reason}</p> : null}
            <p className="text-sm">Upload the file again to validate it from the start.</p>
            {uploadAgain}
          </AlertDescription>
        </Alert>
      );
    case "DISCARDED":
      return (
        <Alert tone="neutral">
          <CircleSlash aria-hidden />
          <AlertDescription>
            {expiredAutomatically(record) ? (
              <p>This preview expired after 24 hours, because store data may have changed since validation. Upload the file again.</p>
            ) : (
              <p>
                Discarded on <DateTime value={record.updated_at} />. No data was changed.
              </p>
            )}
            {again ? (
              <Link href={again} className="text-link hover:underline">
                Upload again
              </Link>
            ) : null}
          </AlertDescription>
        </Alert>
      );
    default:
      return null;
  }
}

/**
 * One import: the wizard's preview and apply steps while it is `VALIDATED`, then its permanent
 * record (SCREEN_SPECIFICATIONS S-12, S-13). The server status drives what is shown.
 */
export function ImportScreen() {
  const store = useStore();
  const now = useNow();
  const { importId } = useParams<{ importId: string }>();
  const canRead = store.permissions.has("imports.read");
  const runGate = usePermission("imports.run");
  const [step, setStep] = useState<"preview" | "apply">("preview");
  const [discarding, setDiscarding] = useState(false);

  const query = useQuery({
    queryKey: importKeys.detail(store.id, importId),
    queryFn: ({ signal }) => importsApi.get(store.id, importId, signal),
    enabled: canRead,
    refetchInterval: (q) => (q.state.data && IN_FLIGHT.includes(q.state.data.status) ? POLL_MS : false),
  });
  useDocumentTitle(query.data?.original_filename ?? "Import");

  if (!canRead) return <PermissionDenied pageName="imports" permission="imports.read" />;

  const listHref = `/s/${store.id}/imports`;
  const breadcrumb = (
    <nav aria-label="Breadcrumb" className="text-sm">
      <ol className="flex min-w-0 items-center gap-1 text-muted-foreground">
        <li>
          <Link href={listHref} className="hover:text-foreground hover:underline">
            Imports
          </Link>
        </li>
        <li aria-hidden>
          <ChevronRight className="size-3.5" />
        </li>
        <li aria-current="page" className="min-w-0 truncate text-foreground">
          {query.data?.original_filename ?? "Import"}
        </li>
      </ol>
    </nav>
  );

  if (query.isPending) {
    return (
      <div aria-busy="true" className="flex flex-col gap-4">
        {breadcrumb}
        <span className="sr-only" role="status">
          Loading import
        </span>
        <Skeleton className="h-7 w-72" />
        <Skeleton className="h-6 w-96" />
        <div className="grid grid-cols-2 gap-3 md:grid-cols-6">
          {[0, 1, 2, 3, 4, 5].map((tile) => (
            <Skeleton key={tile} className="h-16" />
          ))}
        </div>
      </div>
    );
  }
  if (query.isError) {
    if (isApiError(query.error) && query.error.status === 404) {
      return <NotFoundState entity="import" backHref={listHref} backLabel="Back to imports" />;
    }
    return (
      <div className="flex flex-col gap-4">
        {breadcrumb}
        <ErrorState size="page" title="Couldn't load this import" error={query.error} onRetry={() => void query.refetch()} />
      </div>
    );
  }

  const record = query.data;
  const inWizard = record.status === "VALIDATED" || record.status === "APPLYING";
  const applied = record.status === "COMPLETED" || record.status === "COMPLETED_WITH_ERRORS";
  const stepIndex = record.status === "APPLYING" || step === "apply" ? 2 : 1;
  const next = IMPORT_TYPE_INFO[record.import_type].next ?? record.import_type;
  const anotherHref = newImportHref(store, next);

  return (
    <div className="flex flex-col gap-6">
      {breadcrumb}
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <h1 tabIndex={-1} className="min-w-0 font-mono text-title-lg break-all outline-none">
            {record.original_filename}
          </h1>
          <ImportStatusPill status={record.status} size="md" />
        </div>
        <p className="text-sm text-muted-foreground">
          {importTypeLabels[record.import_type]} · {formatQuantity(record.summary.rows_total)} rows · {formatFileSize(record.size_bytes)} · Uploaded{" "}
          <DateTime value={record.created_at} />
        </p>
        {record.status === "VALIDATED" && record.expires_at ? (
          <p className="text-sm text-muted-foreground">Preview expires in {expiresIn(record.expires_at, now)}</p>
        ) : null}
      </div>

      {inWizard ? <Stepper current={stepIndex} /> : null}
      {IN_FLIGHT.includes(record.status) ? (
        <Alert tone="info">
          <Info aria-hidden />
          <AlertDescription>
            <p>{record.status === "APPLYING" ? "Applying… This runs in one transaction. If anything fails, no data changes." : "Validating the file…"}</p>
          </AlertDescription>
        </Alert>
      ) : null}

      {record.status === "VALIDATED" && step === "apply" ? (
        <>
          <PreviewTiles record={record} />
          <ApplyStep record={record} onBack={() => setStep("preview")} />
        </>
      ) : record.status === "VALIDATED" ? (
        <>
          <PreviewTiles record={record} />
          <WarningCallouts record={record} />
          <ExpectedChanges
            rows={record.summary.preview ?? []}
            listed={record.summary.creates + record.summary.updates + record.summary.rows_with_errors}
          />
          <IssueTable
            record={record}
            emptyText={`No issues found. All ${formatQuantity(record.summary.rows_total)} rows are valid.`}
          />
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <ActionButton gate={runGate} variant="secondary" onClick={() => setDiscarding(true)}>
              Discard import
            </ActionButton>
            <ActionButton gate={runGate} onClick={() => setStep("apply")}>
              Continue to apply
              <ChevronRight aria-hidden />
            </ActionButton>
          </div>
          <DiscardDialog record={record} open={discarding} onOpenChange={setDiscarding} />
        </>
      ) : null}

      {!inWizard && !IN_FLIGHT.includes(record.status) ? (
        <>
          <Outcome record={record} />
          {applied ? <AppliedTiles record={record} /> : record.status !== "REJECTED" ? <PreviewTiles record={record} /> : null}
          {/* Evaluation runs are read with exceptions.read. */}
          {applied && store.permissions.has("exceptions.read") ? <EvaluationPanel record={record} /> : null}
          {applied && record.import_type === "products" && (record.summary.applied?.creates ?? 0) > 0 ? (
            <Alert tone="info">
              <Info aria-hidden />
              <AlertDescription>
                <p>New active products have no stock yet, so they appear as Out of stock until you import inventory adjustments.</p>
              </AlertDescription>
            </Alert>
          ) : null}
          {record.status === "REJECTED" ? (
            // The whole file was rejected, so no rows were checked and the callout is the only issue.
            <div className="max-w-xl">
              <Details record={record} />
            </div>
          ) : (
            <div className="grid grid-cols-1 items-start gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
              <IssueTable record={record} emptyText="No issues. Every row was valid." />
              <Details record={record} />
            </div>
          )}
          {applied ? (
            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <Button asChild variant="secondary">
                <Link href={listHref}>Back to imports</Link>
              </Button>
              {anotherHref ? (
                <Button asChild>
                  <Link href={anotherHref}>Import another file</Link>
                </Button>
              ) : null}
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

