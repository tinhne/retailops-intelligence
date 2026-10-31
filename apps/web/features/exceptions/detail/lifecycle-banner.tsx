"use client";

import { ChevronRight, CircleCheck, Hourglass, Info, RotateCcw, Slash } from "lucide-react";
import Link from "next/link";

import { DateTime } from "@/components/data/values";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { CopyButton } from "@/components/states/copy-button";
import type { ExceptionDetail, ExceptionEvent } from "@/lib/api/exceptions-api";
import { categoryLabels, dismissalReasonLabels, exceptionTypeLabels, resolutionCodeLabels } from "@/lib/status-maps";
import { useStore } from "@/lib/store/store-context";

const exceptionHref = (storeId: string, id: string) => `/s/${storeId}/exceptions/${id}`;

/**
 * Where the exception is in its lifecycle and why (S-04 lifecycle banner, C-60). Manual
 * resolutions say plainly that they wait for verification and may reopen.
 */
export function LifecycleBanner({ exception, latestReopen }: { exception: ExceptionDetail; latestReopen?: ExceptionEvent }) {
  const store = useStore();
  const resolution = exception.resolution;
  const dismissal = exception.dismissal;
  let banner: React.ReactNode = null;

  if (exception.status === "RESOLVED" && resolution) {
    const by = resolution.resolved_by?.full_name ?? "a team member";
    const code = resolution.resolution_code ? resolutionCodeLabels[resolution.resolution_code] : null;
    if (resolution.resolution_code === "SUPERSEDED" && exception.superseded_by) {
      banner = (
        <Alert tone="neutral">
          <Info aria-hidden />
          <AlertDescription>
            <p>
              Superseded {resolution.resolved_at ? <>at <DateTime value={resolution.resolved_at} /> </> : null}by{" "}
              <Link href={exceptionHref(store.id, exception.superseded_by.id)} className="text-link hover:underline">
                {exception.superseded_by.reference}
              </Link>{" "}
              ({exceptionTypeLabels[exception.superseded_by.exception_type]}). Work continues there.
            </p>
          </AlertDescription>
        </Alert>
      );
    } else if (resolution.resolution_code === "CONDITION_CLEARED") {
      banner = (
        <Alert tone="success">
          <CircleCheck aria-hidden />
          <AlertDescription>
            <p>
            Resolved automatically{resolution.resolved_at ? <> at <DateTime value={resolution.resolved_at} /></> : null}. The condition
            cleared during an evaluation.
          </p>
          </AlertDescription>
        </Alert>
      );
    } else if (resolution.verified_at) {
      banner = (
        <Alert tone="success">
          <CircleCheck aria-hidden />
          <AlertDescription>
            <p>
            Verified at <DateTime value={resolution.verified_at} />. The condition was no longer detected after {by} resolved it.
          </p>
          </AlertDescription>
        </Alert>
      );
    } else {
      banner = (
        <Alert tone="info">
          <Hourglass aria-hidden />
          <AlertDescription>
            <p>
            Resolved by {by}
            {resolution.resolved_at ? <> at <DateTime value={resolution.resolved_at} /></> : null}
            {code ? ` (${code})` : ""}. Awaiting verification: RetailOps re-checks the condition after the next import completes,
            or after 24 h, whichever comes first. If it is still present then, this exception reopens.
          </p>
          </AlertDescription>
        </Alert>
      );
    }
  } else if (exception.status === "DISMISSED" && dismissal) {
    banner = (
      <Alert tone="neutral">
        <Slash aria-hidden />
        <AlertDescription>
            <p>
          Dismissed by {dismissal.dismissed_by?.full_name ?? "a team member"}
          {dismissal.dismissed_at ? <> at <DateTime value={dismissal.dismissed_at} /></> : null}
          {dismissal.dismissed_reason ? ` · ${dismissalReasonLabels[dismissal.dismissed_reason].label}` : ""}
          {dismissal.note ? `: ${dismissal.note}` : ""}
        </p>
          </AlertDescription>
      </Alert>
    );
  } else if (exception.status === "REOPENED" && latestReopen) {
    const payload = (latestReopen.payload ?? {}) as Record<string, unknown>;
    const reason = String(payload.reason ?? "");
    const note = typeof payload.note === "string" ? payload.note.trim().replace(/\.$/, "") : "";
    const at = <DateTime value={latestReopen.occurred_at} />;
    banner = (
      <Alert tone="warning">
        <RotateCcw aria-hidden />
        <AlertDescription>
          {reason === "VERIFICATION_FAILED" ? (
            <p>
              Reopened at {at}: verification failed. The condition was still present after the data was refreshed (or 24 h
              after it was resolved). The due date was recalculated from the reopen time.
            </p>
          ) : reason === "RECURRED_WITHIN_WINDOW" ? (
            <p>
              Reopened at {at}. The condition came back soon after it was resolved. The due date was recalculated from the
              reopen time.
            </p>
          ) : (
            <p>
              Reopened by {latestReopen.actor?.full_name ?? "a team member"} at {at}
              {note ? `: ${note}` : ""}. The due date was recalculated from the reopen time, and any manual due date was cleared.
            </p>
          )}
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <>
      {banner}
      {exception.previous_occurrence ? (
        <p className="text-sm text-muted-foreground">
          This condition occurred before:{" "}
          <Link href={exceptionHref(store.id, exception.previous_occurrence.id)} className="text-link hover:underline">
            {exception.previous_occurrence.reference}
          </Link>
          .
        </p>
      ) : null}
    </>
  );
}

/** Facts about the exception itself, with the raw identifiers folded away (S-04 "Details"). */
export function DetailsCard({ exception }: { exception: ExceptionDetail }) {
  const entity = exception.primary_entity;
  const rows: Array<[string, React.ReactNode]> = [
    ["Entity", `${entity.type === "product" ? "Product" : "Order"} ${entity.label}${entity.name ? ` (${entity.name})` : ""}`],
    ["Category", categoryLabels[exception.category]],
    ["Type", exceptionTypeLabels[exception.exception_type]],
    ["Detections", String(exception.detection_count)],
    ["Reopens", String(exception.reopen_count)],
  ];
  if (exception.resolution?.resolution_note) rows.push(["Resolution note", exception.resolution.resolution_note]);
  if (exception.supersedes.length) rows.push(["Supersedes", exception.supersedes.map((ref) => ref.reference).join(", ")]);

  return (
    <section aria-labelledby="details-title" className="rounded-lg border bg-card p-4 md:p-5">
      <h2 id="details-title" className="text-title-sm">
        Details
      </h2>
      <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-body">
        {rows.map(([term, value]) => (
          <div key={term} className="contents">
            <dt className="text-muted-foreground">{term}</dt>
            <dd className="min-w-0 break-words">{value}</dd>
          </div>
        ))}
      </dl>
      <Collapsible className="mt-3 border-t pt-3">
        <CollapsibleTrigger className="group flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ChevronRight aria-hidden className="size-4 transition-transform group-data-[state=open]:rotate-90" />
          Technical details
        </CollapsibleTrigger>
        <CollapsibleContent>
          <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
            <dt className="text-muted-foreground">ID</dt>
            <dd className="flex min-w-0 items-center gap-1">
              <code className="truncate font-mono text-mono">{exception.id}</code>
              <CopyButton value={exception.id} label="Copy exception ID" />
            </dd>
            <dt className="text-muted-foreground">Dedup key</dt>
            <dd className="min-w-0 break-all font-mono text-mono">{exception.dedup_key}</dd>
            <dt className="text-muted-foreground">Version</dt>
            <dd className="font-mono text-mono">{exception.version}</dd>
          </dl>
        </CollapsibleContent>
      </Collapsible>
    </section>
  );
}
