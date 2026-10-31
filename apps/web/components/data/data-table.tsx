"use client";

import { Fragment } from "react";

import { ErrorState } from "@/components/states/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export type Column<T> = {
  id: string;
  header: string;
  cell: (row: T) => React.ReactNode;
  align?: "left" | "right";
  hideBelow?: "md" | "lg" | "xl" | "2xl";
  /** Stays in view while the table scrolls sideways (the first column only). */
  pinned?: boolean;
  className?: string;
};

type DataTableProps<T> = {
  /** Visually hidden caption; include page and sort so screen readers know where they are. */
  caption: string;
  columns: Column<T>[];
  rows: T[] | undefined;
  getRowId: (row: T) => string;
  status: "loading" | "error" | "success";
  /** Background refetch or page change: rows stay, dimmed (C-30). */
  isFetching?: boolean;
  error?: unknown;
  onRetry?: () => void;
  errorTitle: string;
  isFiltered: boolean;
  empty: React.ReactNode;
  noResults: React.ReactNode;
  /** Stacked rendering for screens below 768 px (DESIGN_SYSTEM §11.5). */
  renderStackedRow?: (row: T) => React.ReactNode;
  /**
   * Inline expansion (S-15): content for a full-width row below the row, or `null` while the
   * row is collapsed. The disclosure button lives in one of the row's cells.
   */
  renderExpanded?: (row: T) => React.ReactNode;
  density?: "comfortable" | "compact";
};

const hide: Record<NonNullable<Column<unknown>["hideBelow"]>, string> = {
  md: "hidden md:table-cell",
  lg: "hidden lg:table-cell",
  xl: "hidden xl:table-cell",
  "2xl": "hidden 2xl:table-cell",
};

/**
 * Server-paginated list (COMPONENT_INVENTORY C-30). Sorting, filtering and paging happen in the
 * API, so this is a plain table. Each row's primary cell holds one real link stretched over the
 * row, so the row is clickable, middle-click works and screen readers hear one link per row.
 */
export function DataTable<T>({
  caption,
  columns,
  rows,
  getRowId,
  status,
  isFetching = false,
  error,
  onRetry,
  errorTitle,
  isFiltered,
  empty,
  noResults,
  renderStackedRow,
  renderExpanded,
  density = "comfortable",
}: DataTableProps<T>) {
  if (status === "error") return <ErrorState title={errorTitle} error={error} onRetry={onRetry} />;

  if (status === "success" && rows && rows.length === 0) return <>{isFiltered ? noResults : empty}</>;

  const rowHeight = density === "comfortable" ? "h-11" : "h-9";
  const cellX = density === "comfortable" ? "px-3" : "px-2";
  const loading = status === "loading";

  return (
    <div aria-busy={loading || isFetching || undefined}>
      {renderStackedRow ? (
        <ul className={cn("md:hidden", isFetching && "opacity-60")} aria-label={caption}>
          {loading
            ? [0, 1, 2, 3].map((index) => (
                <li key={index} className="border-b p-4">
                  <Skeleton className="h-16 w-full" />
                </li>
              ))
            : rows?.map((row) => (
                <li key={getRowId(row)} className="relative border-b last:border-b-0 hover:bg-surface-hover">
                  {renderStackedRow(row)}
                </li>
              ))}
        </ul>
      ) : null}
      <div className={cn("relative overflow-x-auto", renderStackedRow && "hidden md:block")}>
        <table className={cn("w-full border-collapse", density === "comfortable" ? "text-body" : "text-sm")}>
          <caption className="sr-only">{caption}</caption>
          <thead className="bg-surface-subtle">
            <tr>
              {columns.map((column) => (
                <th
                  key={column.id}
                  scope="col"
                  className={cn(
                    "h-9 border-b text-xs font-medium whitespace-nowrap text-muted-foreground first:pl-4 last:pr-4",
                    cellX,
                    column.align === "right" ? "text-right" : "text-left",
                    column.hideBelow && hide[column.hideBelow],
                    column.pinned && "sticky left-0 z-[1] bg-surface-subtle",
                  )}
                >
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className={cn(isFetching && "opacity-60")}>
            {loading
              ? Array.from({ length: 8 }, (_, index) => (
                  <tr key={index} className={cn("border-b", rowHeight)}>
                    {columns.map((column) => (
                      <td key={column.id} className={cn(cellX, "first:pl-4 last:pr-4", column.hideBelow && hide[column.hideBelow])}>
                        <Skeleton className="h-4 w-full max-w-40" />
                      </td>
                    ))}
                  </tr>
                ))
              : rows?.map((row) => {
                  const expanded = renderExpanded?.(row) ?? null;
                  return (
                    <Fragment key={getRowId(row)}>
                      <tr
                        className={cn(
                          "group/row relative hover:bg-surface-hover",
                          expanded === null && "border-b last:border-b-0",
                          rowHeight,
                        )}
                      >
                        {columns.map((column) => (
                          <td
                            key={column.id}
                            className={cn(
                              cellX,
                              "py-2 align-middle first:pl-4 last:pr-4",
                              column.align === "right" ? "text-right tabular-nums" : "text-left",
                              column.hideBelow && hide[column.hideBelow],
                              column.pinned && "sticky left-0 z-[1] bg-card group-hover/row:bg-surface-hover",
                              column.className,
                            )}
                          >
                            {column.cell(row)}
                          </td>
                        ))}
                      </tr>
                      {expanded !== null ? (
                        <tr className="border-b last:border-b-0">
                          <td colSpan={columns.length} className="px-4 pt-1 pb-3">
                            {expanded}
                          </td>
                        </tr>
                      ) : null}
                    </Fragment>
                  );
                })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
