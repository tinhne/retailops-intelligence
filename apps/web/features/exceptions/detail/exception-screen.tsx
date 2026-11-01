"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { NotFoundState } from "@/components/states/not-found-state";
import { ErrorState } from "@/components/states/error-state";
import { PermissionDenied } from "@/components/states/permission-denied";
import { Skeleton } from "@/components/ui/skeleton";
import { isApiError } from "@/lib/api/errors";
import { exceptionKeys, exceptionsApi } from "@/lib/api/exceptions-api";
import { useDocumentTitle } from "@/lib/hooks/use-document-title";
import { exceptionStatusLabels } from "@/lib/status-maps";
import { useStore } from "@/lib/store/store-context";

import { cn } from "@/lib/utils";

import { LAST_LIST_KEY } from "../inbox-screen";
import { getExceptionActions } from "./actions";
import { Activity } from "./activity";
import { ExceptionHeader } from "./exception-header";
import { AffectedOrders, CalculationBlock, EvidenceTable, hasAffectedSection, PriorityBreakdown, RecommendedAction } from "./investigation";
import { DetailsCard, LifecycleBanner } from "./lifecycle-banner";
import { OnThisPage, type PageSection } from "./on-this-page";
import { QueueNav } from "./queue-nav";
import { isOwnVersion } from "./use-exception-command";

/** The list the person came from, so the breadcrumb returns to the same filters and page. */
function useListHref(storeId: string): string {
  const [href] = useState(() => {
    const fallback = `/s/${storeId}/exceptions`;
    try {
      const remembered = window.sessionStorage.getItem(LAST_LIST_KEY);
      return remembered?.startsWith(fallback) ? remembered : fallback;
    } catch {
      return fallback;
    }
  });
  return href;
}

/** Everything needed to understand and act on one exception (SCREEN_SPECIFICATIONS S-04). */
export function ExceptionScreen() {
  const store = useStore();
  const { exceptionId } = useParams<{ exceptionId: string }>();
  const listHref = useListHref(store.id);
  const canRead = store.permissions.has("exceptions.read");

  const detail = useQuery({
    queryKey: exceptionKeys.detail(store.id, exceptionId),
    queryFn: ({ signal }) => exceptionsApi.detail(store.id, exceptionId, signal),
    refetchInterval: 60_000,
    enabled: canRead,
  });
  const reopenEvents = useQuery({
    queryKey: [...exceptionKeys.events(store.id, exceptionId), "latest", detail.data?.version],
    queryFn: ({ signal }) => exceptionsApi.events(store.id, exceptionId, { page_size: 100 }, signal),
    enabled: canRead && detail.data?.status === "REOPENED",
    select: (page) => [...page.items].reverse().find((event) => event.event_type === "REOPENED"),
  });
  useDocumentTitle(detail.data?.reference ?? "Exception");

  // "Changed by others" (S-04): a refetch that brings someone else's status or assignee change.
  const seen = useRef<{ version: number; status: string; assignee: string | null } | null>(null);
  useEffect(() => {
    const data = detail.data;
    if (!data) return;
    const previous = seen.current;
    seen.current = { version: data.version, status: data.status, assignee: data.assignee?.id ?? null };
    if (!previous || data.version <= previous.version || isOwnVersion(data.id, data.version)) return;
    if (data.status !== previous.status) {
      toast.info(`Updated: status is now ${exceptionStatusLabels[data.status]}`);
    } else if ((data.assignee?.id ?? null) !== previous.assignee) {
      toast.info(`Updated: ${data.assignee ? `assigned to ${data.assignee.full_name}` : "the assignee was removed"}`);
    }
  }, [detail.data]);

  if (!canRead) return <PermissionDenied pageName="exceptions" permission="exceptions.read" />;

  const breadcrumb = (
    <nav aria-label="Breadcrumb" className="text-sm">
      <ol className="flex items-center gap-1 text-muted-foreground">
        <li>
          <Link href={listHref} className="hover:text-foreground hover:underline">
            Exceptions
          </Link>
        </li>
        <li aria-hidden>
          <ChevronRight className="size-3.5" />
        </li>
        <li aria-current="page" className="text-foreground">
          {detail.data?.reference ?? "Exception"}
        </li>
      </ol>
    </nav>
  );

  if (detail.isPending) {
    return (
      <div aria-busy="true" className="flex flex-col gap-4">
        {breadcrumb}
        <span className="sr-only" role="status">
          Loading exception
        </span>
        <Skeleton className="h-7 w-2/3" />
        <div className="flex gap-2">
          <Skeleton className="h-6 w-20" />
          <Skeleton className="h-6 w-24" />
          <Skeleton className="h-6 w-20" />
        </div>
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (detail.isError) {
    if (isApiError(detail.error) && detail.error.status === 404) {
      return <NotFoundState entity="exception" backHref={listHref} backLabel="Back to exceptions" />;
    }
    return (
      <div className="flex flex-col gap-4">
        {breadcrumb}
        <ErrorState size="page" title="Couldn't load this exception" error={detail.error} onRetry={() => void detail.refetch()} />
      </div>
    );
  }

  const exception = detail.data;
  const layout = getExceptionActions(exception, store.organization.isDemo);
  const hasActions = Boolean(layout.primary || layout.secondary.length || layout.more.length);
  const affected = hasAffectedSection(exception);
  const sections: PageSection[] = [
    { id: "priority", label: "Why this priority" },
    { id: "calculation", label: "How this was detected" },
    { id: "evidence", label: "Evidence" },
    ...(affected ? [{ id: "affected", label: "Affected orders" }] : []),
    { id: "activity", label: "Activity" },
    { id: "details", label: "Details" },
  ];
  return (
    // Below 768 px the actions sit in a fixed 64 px bar, so the page keeps room for it.
    <div className={cn("flex flex-col gap-6", hasActions && "pb-20 md:pb-0")}>
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        {breadcrumb}
        <QueueNav exceptionId={exception.id} />
      </div>
      <ExceptionHeader exception={exception} />
      <LifecycleBanner exception={exception} latestReopen={reopenEvents.data} />
      <OnThisPage sections={sections} />
      <div className="grid grid-cols-1 items-start gap-6 xl:grid-cols-[minmax(0,1fr)_var(--aside-w)]">
        <div className="flex min-w-0 flex-col gap-6">
          <RecommendedAction exception={exception} />
          <PriorityBreakdown exception={exception} />
          <CalculationBlock exception={exception} />
          <EvidenceTable exception={exception} />
          <AffectedOrders exception={exception} />
          <Activity exception={exception} />
        </div>
        <aside aria-label="About this exception" className="flex flex-col gap-6 xl:sticky xl:top-20">
          <DetailsCard exception={exception} />
        </aside>
      </div>
    </div>
  );
}
