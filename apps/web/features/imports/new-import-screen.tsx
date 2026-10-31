"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, CircleAlert, FileText, Info, Upload, X } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useId, useState } from "react";

import { PageHeader } from "@/components/shell/page-header";
import { PermissionDenied } from "@/components/states/permission-denied";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { isApiError, userMessage } from "@/lib/api/errors";
import { importKeys, importsApi } from "@/lib/api/imports-api";
import type { UploadProgress } from "@/lib/api/upload";
import { useDocumentTitle } from "@/lib/hooks/use-document-title";
import { IMPORT_TYPES_IN_ORDER, importTypeLabels, type ImportType } from "@/lib/status-maps";
import { useStore } from "@/lib/store/store-context";
import { cn } from "@/lib/utils";

import { IMPORT_COLUMNS, IMPORT_TYPE_INFO } from "./contracts";
import { useDownload } from "./import-actions";
import { formatFileSize } from "./shared";

const MAX_BYTES = 5 * 1024 * 1024;

const megabytes = (bytes: number) => `${(bytes / (1024 * 1024)).toFixed(1)} MB`;

/** Client checks before upload (S-12 "Validation error (client)"). The server checks again. */
export function fileProblem(file: File | null): string | null {
  if (!file) return "Choose a CSV file.";
  if (!file.name.toLowerCase().endsWith(".csv")) return "Only .csv files can be imported.";
  if (file.size > MAX_BYTES) return `This file is ${megabytes(file.size)}. The limit is 5 MB. Split it into smaller files.`;
  return null;
}

function FieldError({ id, message }: { id: string; message: string | null }) {
  if (!message) return null;
  return (
    <p id={id} className="flex items-center gap-1 text-sm text-tone-danger-fg">
      <CircleAlert aria-hidden className="size-4 shrink-0" />
      {message}
    </p>
  );
}

const percent = (progress: UploadProgress) =>
  progress.phase === "uploading" && progress.fraction !== null ? Math.min(100, Math.round(progress.fraction * 100)) : null;

/** "Uploading 42%…" while the bytes go up, then "Validating…" while the API checks every row. */
export function pendingText(progress: UploadProgress): string {
  if (progress.phase === "processing") return "Validating…";
  const value = percent(progress);
  return value === null ? "Uploading…" : `Uploading ${value}%…`;
}

/**
 * Upload progress (S-12 "Pending action"): a determinate bar while the file is sent, then an
 * indeterminate one while the same request validates it. Only the phase is announced.
 */
function UploadStatus({ progress }: { progress: UploadProgress }) {
  const value = percent(progress);
  const validating = progress.phase === "processing";
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between gap-2 text-sm">
        <span role="status">{validating ? "Validating… Every row is checked against the store's data." : "Uploading…"}</span>
        {value !== null ? <span className="text-muted-foreground tabular-nums">{value}%</span> : null}
      </div>
      <div
        role="progressbar"
        aria-label={validating ? "Validating the file" : "Upload progress"}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={value ?? undefined}
        className="h-1.5 w-full overflow-hidden rounded-full bg-muted"
      >
        <div
          className={cn("h-full rounded-full bg-primary", value === null ? "w-full animate-skeleton opacity-60" : "transition-[width] duration-150")}
          style={value === null ? undefined : { width: `${value}%` }}
        />
      </div>
    </div>
  );
}

function ColumnReference({ type }: { type: ImportType }) {
  const [open, setOpen] = useState(false);
  return (
    <Collapsible open={open} onOpenChange={setOpen} className="rounded-lg border">
      <CollapsibleTrigger className="flex w-full items-center gap-2 px-4 py-3 text-left text-body font-medium">
        {open ? <ChevronDown aria-hidden className="size-4" /> : <ChevronRight aria-hidden className="size-4" />}
        Column reference: {type}.csv
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="relative overflow-x-auto border-t">
          <table className="w-full text-sm">
            <caption className="sr-only">Columns of {type}.csv</caption>
            <thead className="bg-surface-subtle text-xs text-muted-foreground">
              <tr>
                <th scope="col" className="px-4 py-2 text-left font-medium">Column</th>
                <th scope="col" className="px-3 py-2 text-left font-medium">Required</th>
                <th scope="col" className="px-4 py-2 text-left font-medium">Type and validation</th>
              </tr>
            </thead>
            <tbody>
              {IMPORT_COLUMNS[type].map((column) => (
                <tr key={column.name} className="border-t">
                  <td className="px-4 py-2 font-mono text-mono whitespace-nowrap">{column.name}</td>
                  <td className="px-3 py-2">{column.required}</td>
                  <td className="px-4 py-2 text-muted-foreground">{column.rule}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}

/** Step 1 of the import wizard: type, file, upload and validate (SCREEN_SPECIFICATIONS S-12). */
export function NewImportScreen() {
  const store = useStore();
  const router = useRouter();
  const queryClient = useQueryClient();
  const searchParams = useSearchParams();
  useDocumentTitle("New import");
  const preselected = searchParams.get("type");
  const [type, setType] = useState<ImportType | null>(
    IMPORT_TYPES_IN_ORDER.includes(preselected as ImportType) ? (preselected as ImportType) : null,
  );
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const { pending: templatePending, run: download } = useDownload();
  const ids = { type: useId(), file: useId(), fileError: useId(), typeError: useId() };
  const [progress, setProgress] = useState<UploadProgress | null>(null);

  const upload = useMutation({
    mutationFn: () => {
      setProgress({ phase: "uploading", fraction: 0 });
      return importsApi.upload(store.id, type as ImportType, file as File, setProgress);
    },
    onSuccess: (created) => {
      queryClient.setQueryData(importKeys.detail(store.id, created.id), created);
      void queryClient.invalidateQueries({ queryKey: importKeys.all(store.id) });
      router.replace(`/s/${store.id}/imports/${created.id}`);
    },
  });

  if (!store.permissions.has("imports.run")) return <PermissionDenied pageName="new imports" permission="imports.run" />;

  const typeError = submitted && !type ? "Choose what you're importing." : null;
  // A chosen file is checked at once; a missing one only after a submit attempt.
  const fileError = submitted || file ? fileProblem(file) : null;
  const choose = (next: File | null) => {
    setFile(next);
    upload.reset();
  };
  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitted(true);
    if (!type || fileProblem(file)) return;
    upload.mutate();
  };
  const uploadError = upload.isError
    ? isApiError(upload.error) && upload.error.isNetworkError
      ? "Upload failed. Check your connection and try again."
      : userMessage(upload.error)
    : null;

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <nav aria-label="Breadcrumb" className="text-sm">
        <ol className="flex items-center gap-1 text-muted-foreground">
          <li>
            <Link href={`/s/${store.id}/imports`} className="hover:text-foreground hover:underline">
              Imports
            </Link>
          </li>
          <li aria-hidden>
            <ChevronRight className="size-3.5" />
          </li>
          <li aria-current="page" className="text-foreground">
            New import
          </li>
        </ol>
      </nav>
      <PageHeader title="New import" subtitle="Step 1 of 4 · Upload. Nothing changes until you review the preview and apply." />

      <form onSubmit={submit} noValidate className="flex flex-col gap-6">
        <fieldset className="flex flex-col gap-3" aria-describedby={typeError ? ids.typeError : undefined}>
          <legend className="mb-3 text-title-sm">What are you importing?</legend>
          <RadioGroup
            value={type ?? ""}
            onValueChange={(value) => setType(value as ImportType)}
            className="grid-cols-1 sm:grid-cols-2"
            aria-invalid={typeError ? true : undefined}
          >
            {IMPORT_TYPES_IN_ORDER.map((option, index) => (
              <div
                key={option}
                className={cn(
                  "relative flex gap-3 rounded-lg border bg-card p-4 transition-colors has-[[data-state=checked]]:border-primary has-[[data-state=checked]]:bg-surface-selected",
                )}
              >
                <RadioGroupItem id={`${ids.type}-${option}`} value={option} className="mt-0.5" />
                <div className="flex min-w-0 flex-col gap-1">
                  <label htmlFor={`${ids.type}-${option}`} className="cursor-pointer font-medium after:absolute after:inset-0">
                    {index + 1}. {importTypeLabels[option]}
                  </label>
                  <p className="text-sm text-muted-foreground">{IMPORT_TYPE_INFO[option].description}</p>
                  <button
                    type="button"
                    onClick={() =>
                      void download(option, importsApi.templatePath(store.id, option), `${option}_template.csv`, "Couldn't download the template. Try again.")
                    }
                    disabled={templatePending === option}
                    className="relative z-[1] self-start text-sm text-link hover:underline disabled:opacity-60"
                  >
                    Template {option}.csv
                  </button>
                </div>
              </div>
            ))}
          </RadioGroup>
          <FieldError id={ids.typeError} message={typeError} />
        </fieldset>

        {type ? (
          <>
            {IMPORT_TYPE_INFO[type].hint ? (
              <Alert tone="info">
                <Info aria-hidden />
                <AlertDescription>
                  <p>{IMPORT_TYPE_INFO[type].hint}</p>
                </AlertDescription>
              </Alert>
            ) : null}
            <ColumnReference type={type} />
          </>
        ) : null}

        <div className="flex flex-col gap-2">
          <span id={ids.file} className="text-title-sm">
            File
          </span>
          {file ? (
            <div className="flex items-center gap-3 rounded-lg border bg-card p-4">
              <FileText aria-hidden className="size-5 shrink-0 text-muted-foreground" />
              <div className="min-w-0 flex-1">
                <p className="font-mono text-mono break-all">{file.name}</p>
                <p className="text-sm text-muted-foreground">{formatFileSize(file.size)}</p>
              </div>
              <Button type="button" variant="ghost" size="sm" onClick={() => choose(null)} disabled={upload.isPending}>
                <X aria-hidden />
                Remove
              </Button>
            </div>
          ) : (
            <label
              onDragOver={(event) => {
                event.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(event) => {
                event.preventDefault();
                setDragging(false);
                choose(event.dataTransfer.files[0] ?? null);
              }}
              className={cn(
                "flex cursor-pointer flex-col items-center gap-2 rounded-lg border border-dashed bg-card px-4 py-8 text-center has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-ring",
                dragging && "border-primary bg-surface-selected",
                fileError && "border-tone-danger-fg",
              )}
            >
              <Upload aria-hidden className="size-6 text-muted-foreground" />
              <span className="text-body">
                <span className="font-medium text-link">Choose a CSV file</span> or drag it here
              </span>
              <span className="text-sm text-muted-foreground">.csv, UTF-8, up to 5 MB and 20,000 rows</span>
              <input
                type="file"
                accept=".csv,text/csv"
                className="sr-only"
                aria-labelledby={ids.file}
                aria-describedby={fileError ? ids.fileError : undefined}
                aria-invalid={fileError ? true : undefined}
                onChange={(event) => choose(event.target.files?.[0] ?? null)}
              />
            </label>
          )}
          <FieldError id={ids.fileError} message={fileError} />
        </div>

        {upload.isPending && progress ? <UploadStatus progress={progress} /> : null}

        {uploadError ? (
          <Alert tone="danger" role="alert">
            <CircleAlert aria-hidden />
            <AlertDescription>
              <p>{uploadError}</p>
            </AlertDescription>
          </Alert>
        ) : null}

        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button asChild variant="secondary">
            <Link href={`/s/${store.id}/imports`}>Cancel</Link>
          </Button>
          <Button type="submit" pending={upload.isPending} pendingLabel={progress ? pendingText(progress) : "Uploading…"}>
            Upload and validate
          </Button>
        </div>
      </form>
    </div>
  );
}
