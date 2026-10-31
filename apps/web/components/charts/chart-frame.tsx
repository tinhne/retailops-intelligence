"use client";

import { BarChart3 } from "lucide-react";
import { useState } from "react";

import { EmptyState } from "@/components/states/empty-state";
import { ErrorState } from "@/components/states/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export type ChartTable = {
  columns: Array<{ key: string; header: string; align?: "left" | "right" }>;
  rows: Array<Record<string, React.ReactNode>>;
};

type ChartFrameProps = {
  /** Metric, window and zone: "Shipments per day, last 30 days (ET)". */
  title: string;
  status: "loading" | "error" | "success";
  error?: unknown;
  onRetry?: () => void;
  isEmpty: boolean;
  emptyMessage: string;
  /** Text summary of the data for the chart's accessible name. */
  ariaSummary: string;
  table: ChartTable;
  height: number;
  children: React.ReactNode;
};

/**
 * Chart container (COMPONENT_INVENTORY C-43) with a Chart / Table toggle. The table is a real
 * `<table>` and is the keyboard and screen-reader path to the same numbers.
 */
export function ChartFrame({
  title,
  status,
  error,
  onRetry,
  isEmpty,
  emptyMessage,
  ariaSummary,
  table,
  height,
  children,
}: ChartFrameProps) {
  const [view, setView] = useState<"chart" | "table">("chart");

  return (
    <section aria-labelledby="chart-title" className="flex flex-col gap-3 rounded-lg border bg-card p-4 md:p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="chart-title" className="text-title-sm">
          {title}
        </h2>
        {status === "success" && !isEmpty ? (
          <div role="group" aria-label="Display as" className="inline-flex rounded-md border border-input p-0.5">
            {(["chart", "table"] as const).map((option) => (
              <button
                key={option}
                type="button"
                aria-pressed={view === option}
                onClick={() => setView(option)}
                className={cn(
                  "h-6 rounded-sm px-2 text-xs transition-colors duration-100",
                  view === option ? "bg-muted text-foreground" : "text-muted-foreground hover:bg-accent",
                )}
              >
                {option === "chart" ? "Chart" : "Table"}
              </button>
            ))}
          </div>
        ) : null}
      </div>

      {status === "loading" ? (
        <div aria-busy="true">
          <Skeleton style={{ height }} className="w-full" />
        </div>
      ) : status === "error" ? (
        <ErrorState title="Couldn't load the chart" error={error} onRetry={onRetry} />
      ) : isEmpty ? (
        <EmptyState icon={BarChart3} title={emptyMessage} />
      ) : view === "chart" ? (
        <div role="img" aria-label={ariaSummary} style={{ height }}>
          {children}
        </div>
      ) : (
        <div className="relative max-h-80 overflow-auto rounded-md border">
          <table className="w-full text-sm">
            <caption className="sr-only">{title}</caption>
            <thead className="sticky top-0 bg-surface-subtle">
              <tr>
                {table.columns.map((column) => (
                  <th
                    key={column.key}
                    scope="col"
                    className={cn(
                      "h-9 border-b px-3 text-xs text-muted-foreground",
                      column.align === "right" ? "text-right" : "text-left",
                    )}
                  >
                    {column.header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row, index) => (
                <tr key={index} className="border-b last:border-b-0">
                  {table.columns.map((column) => (
                    <td
                      key={column.key}
                      className={cn("h-9 px-3 tabular-nums", column.align === "right" ? "text-right" : "text-left")}
                    >
                      {row[column.key]}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
