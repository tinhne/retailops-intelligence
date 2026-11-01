"use client";

import Link from "next/link";

import type { Column } from "@/components/data/data-table";
import { DateTime, DueLabel, Money, NoValue } from "@/components/data/values";
import { ExceptionStatusPill, PriorityIndicator, SeverityBadge } from "@/components/status/status-pill";
import type { ExceptionListItem } from "@/lib/api/exceptions-api";
import { formatDateTime, formatRelative } from "@/lib/format/datetime";
import { formatCount } from "@/lib/format/number";
import { useNow } from "@/lib/hooks/use-now";
import { dismissalReasonLabels, exceptionTypeLabels, resolutionCodeLabels } from "@/lib/status-maps";
import { useStore } from "@/lib/store/store-context";

/** The muted second line: reference · type · entity · orders (S-03 "Exception" column). */
export function ExceptionMeta({ item }: { item: ExceptionListItem }) {
  const parts = [exceptionTypeLabels[item.exception_type], item.primary_entity.label];
  if (item.affected_order_count > 0) parts.push(formatCount(item.affected_order_count, "order"));
  if (item.resolution_code) parts.push(resolutionCodeLabels[item.resolution_code]);
  if (item.dismissed_reason) parts.push(dismissalReasonLabels[item.dismissed_reason].label);
  return (
    <span className="text-sm text-muted-foreground">
      <span className="font-medium text-foreground">{item.reference}</span> · {parts.join(" · ")}
    </span>
  );
}

function Status({ item }: { item: ExceptionListItem }) {
  return (
    <ExceptionStatusPill status={item.status} resolutionCode={item.resolution_code} verifiedAt={item.verified_at} />
  );
}

function Assignee({ item }: { item: ExceptionListItem }) {
  return item.assignee ? (
    <span className="truncate">{item.assignee.full_name}</span>
  ) : (
    <span className="text-muted-foreground">Unassigned</span>
  );
}

/** Accessible name of a row link: reference, title, severity, priority and status (C-62). */
export function rowLabel(item: ExceptionListItem): string {
  return `${item.reference}, ${item.title}`;
}

/** "Last detected": relative time, the full date in the tooltip (S-03, optional column). */
function LastDetected({ item }: { item: ExceptionListItem }) {
  const { timezone } = useStore();
  const now = useNow();
  return (
    <time dateTime={item.last_detected_at} title={formatDateTime(item.last_detected_at, timezone, now)} className="whitespace-nowrap text-sm">
      {formatRelative(item.last_detected_at, timezone, now)}
    </time>
  );
}

export function exceptionColumns(
  hrefFor: (item: ExceptionListItem) => string,
  closedView: boolean,
  options: { lastDetected?: boolean } = {},
): Column<ExceptionListItem>[] {
  const lastDetected: Column<ExceptionListItem>[] = options.lastDetected
    ? [{ id: "last_detected", header: "Last detected", hideBelow: "xl", cell: (item) => <LastDetected item={item} /> }]
    : [];
  return [
    {
      id: "priority",
      header: "Priority",
      cell: (item) => <PriorityIndicator band={item.priority_band} score={item.priority_score} />,
      className: "w-28",
    },
    {
      id: "exception",
      header: "Exception",
      cell: (item) => (
        <div className="flex min-w-60 flex-col gap-0.5 py-1">
          <Link
            href={hrefFor(item)}
            aria-label={rowLabel(item)}
            className="line-clamp-2 text-body-strong outline-offset-[-2px] after:absolute after:inset-0 hover:underline"
          >
            {item.title}
          </Link>
          <ExceptionMeta item={item} />
        </div>
      ),
    },
    { id: "severity", header: "Severity", cell: (item) => <SeverityBadge severity={item.severity} /> },
    { id: "status", header: "Status", cell: (item) => <Status item={item} /> },
    {
      id: "risk",
      header: "At risk",
      align: "right",
      hideBelow: "lg",
      cell: (item) => (Number(item.exposure_amount) === 0 ? <NoValue /> : <Money value={item.exposure_amount} />),
    },
    { id: "assignee", header: "Assignee", hideBelow: "md", cell: (item) => <Assignee item={item} />, className: "max-w-40" },
    closedView
      ? {
          id: "closed",
          header: "Closed",
          cell: (item) => (item.closed_at ? <DateTime value={item.closed_at} compact /> : <NoValue />),
          className: "whitespace-nowrap text-sm",
        }
      : {
          id: "due",
          header: "Due",
          cell: (item) => <DueLabel dueAt={item.due_at} className="text-sm" />,
        },
    ...lastDetected,
  ];
}

/** The stacked row for screens below 768 px (DESIGN_SYSTEM §11.5). */
export function StackedExceptionRow({ item, href, closedView }: { item: ExceptionListItem; href: string; closedView: boolean }) {
  return (
    <div className="flex flex-col gap-1.5 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <PriorityIndicator band={item.priority_band} score={item.priority_score} />
        <SeverityBadge severity={item.severity} />
        <span className="ml-auto text-sm">
          {closedView ? item.closed_at ? <DateTime value={item.closed_at} compact /> : null : <DueLabel dueAt={item.due_at} />}
        </span>
      </div>
      <Link href={href} aria-label={rowLabel(item)} className="line-clamp-2 text-body-strong after:absolute after:inset-0">
        {item.title}
      </Link>
      <ExceptionMeta item={item} />
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Status item={item} />
        <Assignee item={item} />
      </div>
    </div>
  );
}
