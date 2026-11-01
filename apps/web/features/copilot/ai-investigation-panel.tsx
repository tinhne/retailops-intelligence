"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader, MessagesSquare, RefreshCw, Sparkles, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";

import { ErrorState } from "@/components/states/error-state";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { copilotApi, type ExceptionSummary } from "@/lib/api/copilot-api";
import type { ExceptionDetail } from "@/lib/api/exceptions-api";
import { useStore } from "@/lib/store/store-context";
import { cn } from "@/lib/utils";

import { CopilotAnswer } from "./copilot-answer";

export const summaryKey = (storeId: string, exceptionId: string) => ["store", storeId, "copilot", "summary", exceptionId] as const;

function Elapsed() {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const started = Date.now();
    const timer = window.setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => window.clearInterval(timer);
  }, []);
  return <span className="tabular-nums">{seconds} s</span>;
}

/** The summary is older than the evidence it explains (C-86 "stale"). */
export function isStale(summary: ExceptionSummary, exception: ExceptionDetail): boolean {
  const generatedAt = summary.meta.cache.generated_at ?? summary.meta.as_of;
  return new Date(generatedAt).getTime() < new Date(exception.last_detected_at).getTime();
}

/**
 * On-demand AI explanation of one exception (COMPONENT_INVENTORY C-86), kept apart from the
 * deterministic sections. Generating is explicit; the result is shared through the query cache,
 * so the aside and the single-column copies of the panel show the same summary.
 */
export function AIInvestigationPanel({ exception, sectionId, className }: { exception: ExceptionDetail; sectionId?: string; className?: string }) {
  const store = useStore();
  const queryClient = useQueryClient();
  const headingId = useId();
  const lastForce = useRef(false);
  const key = summaryKey(store.id, exception.id);
  const summary = useQuery({
    queryKey: key,
    queryFn: () => copilotApi.exceptionSummary(store.id, exception.id, false),
    enabled: false,
    staleTime: Infinity,
    retry: false,
  });
  const canUse = store.permissions.has("copilot.use");

  // Regenerate bypasses the server's summary cache; a retry repeats the last kind of request.
  const generate = (force: boolean) => {
    lastForce.current = force;
    void queryClient
      .fetchQuery({ queryKey: key, queryFn: () => copilotApi.exceptionSummary(store.id, exception.id, force), retry: false })
      .catch(() => undefined);
  };

  const followUpHref = `/s/${store.id}/copilot?context_type=EXCEPTION&context_id=${exception.id}`;
  const fetching = summary.isFetching;

  let body: React.ReactNode;
  if (!canUse) {
    body = (
      <p className="text-body text-muted-foreground">
        {store.organization.isDemo ? "The copilot isn't available to this role." : "The AI investigation needs the Use the copilot permission."}
      </p>
    );
  } else if (fetching) {
    body = (
      <p role="status" className="flex items-center gap-2 text-body text-muted-foreground">
        <Loader aria-hidden className="size-4 animate-spin motion-reduce:animate-none" />
        Reading evidence, history and related records… <Elapsed />
      </p>
    );
  } else if (summary.isError) {
    body = <ErrorState title="The copilot couldn't explain this exception." error={summary.error} onRetry={() => generate(lastForce.current)} />;
  } else if (summary.data) {
    body = (
      <div className="flex flex-col gap-3">
        {isStale(summary.data, exception) ? (
          <Alert tone="warning">
            <TriangleAlert aria-hidden />
            <AlertDescription>
              <p>Evidence changed after this summary was generated. Regenerate to include the latest data.</p>
            </AlertDescription>
          </Alert>
        ) : null}
        <CopilotAnswer answer={summary.data.answer} meta={summary.data.meta} createdAt={summary.data.meta.as_of} variant="compact" />
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="secondary" size="sm" onClick={() => generate(true)}>
            <RefreshCw aria-hidden />
            Regenerate
          </Button>
          <Button asChild variant="secondary" size="sm">
            <Link href={followUpHref}>
              <MessagesSquare aria-hidden />
              Ask a follow-up
            </Link>
          </Button>
        </div>
      </div>
    );
  } else {
    body = (
      <div className="flex flex-col items-start gap-3">
        <p className="text-body text-muted-foreground">Get a plain-language reading of the evidence, the history and the related records.</p>
        <Button type="button" variant="secondary" size="sm" onClick={() => generate(false)}>
          <Sparkles aria-hidden />
          Generate investigation
        </Button>
      </div>
    );
  }

  return (
    <section id={sectionId} aria-labelledby={headingId} className={cn("scroll-mt-20 rounded-lg border bg-card p-4 md:p-5", className)}>
      <div className="mb-3 flex flex-col gap-0.5">
        <h2 id={headingId} className="flex items-center gap-2 text-title-sm">
          <Sparkles aria-hidden className="size-4 text-primary" />
          AI investigation
        </h2>
        <p className="text-xs text-muted-foreground">Explains the evidence. It doesn&apos;t change data.</p>
      </div>
      {body}
      <div aria-live="polite" className="sr-only">
        {summary.data && !fetching ? "AI investigation ready" : ""}
      </div>
    </section>
  );
}
