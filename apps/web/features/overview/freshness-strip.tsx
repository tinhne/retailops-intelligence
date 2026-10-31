"use client";

import { CircleAlert, TriangleAlert } from "lucide-react";

import { DateTime } from "@/components/data/values";
import type { Dashboard } from "@/lib/api/store-api";
import { formatDateTimeCompact } from "@/lib/format/datetime";
import { useNow } from "@/lib/hooks/use-now";
import { evaluationStatusLabels, evaluationTriggerLabels, importTypeLabels } from "@/lib/status-maps";
import { useStore } from "@/lib/store/store-context";

const STALE_ORDERS_HOURS = 24;

/** "2 days ago", "30 hours ago" for the stale-data warning. */
export function staleAge(hours: number): string {
  if (hours < 72) return `${Math.floor(hours)} hours ago`;
  const days = Math.floor(hours / 24);
  return `${days} days ago`;
}

/**
 * Is the data current? The latest evaluation run and the latest applied import per type
 * (S-02 "Freshness strip"). Problems carry an icon and text, never colour alone.
 */
export function FreshnessStrip({ freshness }: { freshness: Dashboard["data_freshness"] }) {
  const { timezone } = useStore();
  const now = useNow();
  const run = freshness.last_evaluation_run;
  const applied = freshness.imports.filter((item) => item.applied_at !== null);
  const orders = freshness.imports.find((item) => item.import_type === "orders");
  const ordersAgeHours = orders?.applied_at
    ? (now.getTime() - new Date(orders.applied_at).getTime()) / 3_600_000
    : null;

  return (
    <div className="flex flex-col gap-1 text-sm text-muted-foreground">
      {run === null ? (
        <p>No analysis has run yet.</p>
      ) : run.status === "RUNNING" ? (
        <p>
          Analysis running · started <DateTime value={run.started_at} compact />
        </p>
      ) : run.status === "FAILED" ? (
        <p className="flex items-center gap-1.5 text-tone-warning-fg">
          <TriangleAlert aria-hidden className="size-4 shrink-0" />
          The last evaluation failed at {formatDateTimeCompact(run.started_at, timezone, now)}. No exceptions were
          changed by it.
        </p>
      ) : run.status === "SKIPPED" ? (
        <p>The last scheduled run was skipped because another analysis was running.</p>
      ) : (
        <p>
          Last evaluation <DateTime value={run.finished_at ?? run.started_at} compact /> ·{" "}
          {evaluationTriggerLabels[run.trigger]} · {evaluationStatusLabels[run.status]}
        </p>
      )}

      {applied.length === 0 ? (
        <p>No CSV imports yet.</p>
      ) : (
        <p>
          Last imports:{" "}
          {applied.map((item, index) => (
            <span key={item.import_type}>
              {index > 0 ? " · " : null}
              {importTypeLabels[item.import_type]} <DateTime value={item.applied_at as string} compact />
            </span>
          ))}
        </p>
      )}

      {ordersAgeHours !== null && ordersAgeHours > STALE_ORDERS_HOURS ? (
        <p className="flex items-center gap-1.5 text-tone-warning-fg">
          <CircleAlert aria-hidden className="size-4 shrink-0" />
          Order data was last imported {staleAge(ordersAgeHours)}. Figures may be out of date.
        </p>
      ) : null}
    </div>
  );
}
