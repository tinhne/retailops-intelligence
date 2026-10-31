"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CircleAlert, Info, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useId, useRef, useState } from "react";

import { ActionButton } from "@/components/actions/action-button";
import { Section } from "@/components/data/section";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { isApiError, userMessage } from "@/lib/api/errors";
import { importKeys, importsApi, type ImportDetail } from "@/lib/api/imports-api";
import { storeKeys } from "@/lib/api/store-api";
import { formatQuantity } from "@/lib/format/number";
import type { Gate } from "@/lib/permissions";
import type { ImportMode, ImportType } from "@/lib/status-maps";
import { usePermission, useStore } from "@/lib/store/store-context";

import { newImportHref } from "./import-actions";

const NOUNS: Record<ImportType, string> = {
  products: "products",
  orders: "orders",
  order_items: "order lines",
  inventory_adjustments: "adjustments",
};

const CASCADE: Partial<Record<ImportType, string>> = {
  orders: "Lines of skipped orders will fail with UNKNOWN_ORDER when you import order items.",
  products: "Adjustments and lines for skipped products will fail with UNKNOWN_SKU.",
};

type Problem = { tone: "danger" | "info"; text: string; uploadAgain?: boolean };

/** What an apply failure means for the person (S-12 "Apply errors"). */
function applyProblem(error: unknown): Problem {
  if (!isApiError(error)) return { tone: "danger", text: userMessage(error) };
  switch (error.code) {
    case "IMPORT_HAS_ERRORS":
      return { tone: "danger", text: "Strict mode can't apply a file with row errors. Choose Valid rows only, or fix the file." };
    case "IMPORT_SKIPPED_ROWS_NOT_CONFIRMED":
      return { tone: "danger", text: "The number of rows to skip changed. Review the issues and confirm again." };
    case "IMPORT_PREVIEW_STALE":
      return {
        tone: "danger",
        text: "Store data changed since the preview, so a different set of rows would be skipped. Nothing was applied.",
        uploadAgain: true,
      };
    case "IDEMPOTENT_REQUEST_IN_PROGRESS":
      return { tone: "info", text: "This apply is already running." };
    default:
      return { tone: "danger", text: `${userMessage(error)}${error.requestId ? ` Request ID ${error.requestId}.` : ""}` };
  }
}

/**
 * Step 3: choose the mode and apply (S-12, BR-606). Valid-rows-only needs consent to the exact
 * number of skipped rows. The Idempotency-Key is made when the step opens, reused when the same
 * attempt is retried, and replaced when the mode changes.
 */
export function ApplyStep({ record, onBack }: { record: ImportDetail; onBack: () => void }) {
  const store = useStore();
  const queryClient = useQueryClient();
  const permission = usePermission("imports.run");
  const { summary } = record;
  const errors = summary.rows_with_errors;
  const valid = summary.rows_total - errors;
  const [mode, setMode] = useState<ImportMode>("STRICT");
  const [consent, setConsent] = useState(false);
  const keyRef = useRef<string | null>(null);
  const consentId = useId();

  const apply = useMutation({
    mutationFn: () => {
      keyRef.current ??= crypto.randomUUID();
      const body = mode === "STRICT" ? { mode } : { mode, confirm_skipped_rows: errors };
      return importsApi.apply(store.id, record.id, body, keyRef.current);
    },
    onSuccess: (updated) => {
      keyRef.current = null;
      queryClient.setQueryData(importKeys.detail(store.id, record.id), updated);
      // Applied data changes stock, orders, exceptions and the dashboard.
      void queryClient.invalidateQueries({ queryKey: storeKeys.all(store.id) });
    },
    onError: (error) => {
      if (!isApiError(error)) return;
      if (error.code === "IMPORT_SKIPPED_ROWS_NOT_CONFIRMED") setConsent(false);
      // These leave the import in a new state; the page renders it.
      if (["IMPORT_PREVIEW_EXPIRED", "IMPORT_NOT_APPLICABLE", "IDEMPOTENT_REQUEST_IN_PROGRESS"].includes(error.code)) {
        void queryClient.invalidateQueries({ queryKey: importKeys.detail(store.id, record.id) });
      }
    },
  });

  const changeMode = (next: ImportMode) => {
    setMode(next);
    setConsent(false);
    keyRef.current = null;
    apply.reset();
  };

  const rows = (count: number) => `${formatQuantity(count)} ${count === 1 ? "row" : "rows"}`;
  const gate: Gate = !permission.allowed
    ? permission
    : mode === "STRICT" && errors > 0
      ? { allowed: false, reason: `Strict mode blocks apply while ${rows(errors)} ${errors === 1 ? "has" : "have"} errors.` }
      : mode === "VALID_ROWS_ONLY" && !consent
        ? { allowed: false, reason: `Confirm that ${rows(errors)} will be skipped.` }
        : { allowed: true };
  const label = mode === "VALID_ROWS_ONLY" ? `Apply ${rows(valid)}, skip ${formatQuantity(errors)}` : `Apply ${rows(summary.rows_total)}`;
  const applying = mode === "VALID_ROWS_ONLY" ? valid : summary.rows_total;
  const problem = apply.isError ? applyProblem(apply.error) : null;
  // A server or network failure is retried with the same key, so it can never apply twice.
  const retryable = apply.isError && (!isApiError(apply.error) || apply.error.isNetworkError || apply.error.status >= 500);
  const noun = NOUNS[record.import_type];

  return (
    <Section id="apply" title="Apply mode">
      <div className="flex flex-col gap-4">
        <RadioGroup value={mode} onValueChange={(value) => changeMode(value as ImportMode)} aria-label="Apply mode" className="gap-4">
          <div className="flex gap-3">
            <RadioGroupItem id="mode-strict" value="STRICT" className="mt-1" />
            <div className="flex flex-col gap-1">
              <label htmlFor="mode-strict" className="font-medium">
                Strict <span className="font-normal text-muted-foreground">(default)</span>
              </label>
              <p className="text-sm text-muted-foreground">Apply only if every row is valid. Nothing is skipped.</p>
              {mode === "STRICT" && errors > 0 ? (
                <p className="flex items-start gap-1.5 text-sm text-tone-warning-fg">
                  <TriangleAlert aria-hidden className="mt-0.5 size-4 shrink-0" />
                  Blocked: {rows(errors)} {errors === 1 ? "has" : "have"} errors. Fix them in the source and upload again, or choose
                  &quot;Valid rows only&quot;.
                </p>
              ) : null}
            </div>
          </div>
          {errors > 0 ? (
            <div className="flex gap-3">
              <RadioGroupItem id="mode-valid" value="VALID_ROWS_ONLY" className="mt-1" />
              <div className="flex flex-col gap-2">
                <label htmlFor="mode-valid" className="font-medium">
                  Valid rows only
                </label>
                <p className="text-sm text-muted-foreground">
                  Apply the {rows(valid)} that are valid and skip the {rows(errors)} with errors. Skipped rows are kept as import issues and can
                  be downloaded.
                </p>
                {mode === "VALID_ROWS_ONLY" ? (
                  <>
                    <label htmlFor={consentId} className="flex cursor-pointer items-center gap-2 text-body">
                      <Checkbox id={consentId} checked={consent} onCheckedChange={(checked) => setConsent(checked === true)} />I understand that{" "}
                      {rows(errors)} will be skipped.
                    </label>
                    {CASCADE[record.import_type] ? <p className="text-sm text-muted-foreground">{CASCADE[record.import_type]}</p> : null}
                  </>
                ) : null}
              </div>
            </div>
          ) : null}
        </RadioGroup>

        <p className="text-body">
          What will change: {formatQuantity(summary.creates)} {noun} created, {formatQuantity(summary.updates)} updated,{" "}
          {formatQuantity(summary.unchanged)} unchanged.
          <span className="block text-sm text-muted-foreground">Applying runs in one transaction. If anything fails, nothing changes.</span>
        </p>

        {problem ? (
          <Alert tone={problem.tone} role={problem.tone === "danger" ? "alert" : "status"}>
            {problem.tone === "danger" ? <CircleAlert aria-hidden /> : <Info aria-hidden />}
            <AlertDescription>
              <p>{problem.text}</p>
              {problem.uploadAgain && newImportHref(store, record.import_type) ? (
                <Link href={newImportHref(store, record.import_type) as string} className="text-link hover:underline">
                  Upload again
                </Link>
              ) : null}
            </AlertDescription>
          </Alert>
        ) : null}

        {apply.isPending ? (
          <p role="status" className="text-sm text-muted-foreground">
            Applying {rows(applying)}… This runs in one transaction. If anything fails, no data changes.
          </p>
        ) : null}

        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button type="button" variant="secondary" onClick={onBack} disabled={apply.isPending}>
            Back
          </Button>
          <ActionButton gate={gate} pending={apply.isPending} pendingLabel={`Applying ${rows(applying)}…`} onClick={() => apply.mutate()}>
            {retryable ? "Try again" : label}
          </ActionButton>
        </div>
      </div>
    </Section>
  );
}
