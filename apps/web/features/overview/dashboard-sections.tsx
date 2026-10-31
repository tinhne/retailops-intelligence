"use client";

import { useQuery } from "@tanstack/react-query";
import { CircleCheck } from "lucide-react";
import Link from "next/link";

import { KpiCard } from "@/components/data/kpi-card";
import { DueLabel, Money, NoValue } from "@/components/data/values";
import { sectionHref } from "@/components/shell/nav-config";
import { EmptyState } from "@/components/states/empty-state";
import { ExceptionStatusPill, PriorityIndicator, SeverityBadge } from "@/components/status/status-pill";
import { storeApi, storeKeys, type AttentionItem, type Dashboard } from "@/lib/api/store-api";
import { formatDateTimeCompact } from "@/lib/format/datetime";
import { formatPercentValue, formatQuantity } from "@/lib/format/number";
import { categoryLabels, stockHealthMeta, type ExceptionCategory, type StockHealth } from "@/lib/status-maps";
import { useStore } from "@/lib/store/store-context";
import { cn } from "@/lib/utils";

/** Total of a filtered exceptions list, read from a one-row page. */
function useExceptionCount(query: Record<string, string | string[]>) {
  const store = useStore();
  const params = { ...query, page_size: 1 };
  return useQuery({
    queryKey: storeKeys.exceptions(store.id, params),
    queryFn: ({ signal }) => storeApi.exceptions(store.id, params, signal),
    select: (page) => page.total,
    enabled: store.permissions.has("exceptions.read"),
  });
}

function MaybeLink({ href, className, children }: { href?: string; className?: string; children: React.ReactNode }) {
  return href ? (
    <Link href={href} className={cn("text-link hover:underline", className)}>
      {children}
    </Link>
  ) : (
    <span className={className}>{children}</span>
  );
}

/** Six headline numbers, each linking to the list behind it once that list exists (S-02). */
export function KpiRow({ dashboard }: { dashboard: Dashboard }) {
  const store = useStore();
  const { active_exceptions: active, orders, on_time_shipment_30_days: onTime } = dashboard;
  const unassignedP1 = useExceptionCount({ assignee: "unassigned", priority_band: "P1" });
  const href = (segment: string, query: Record<string, string | string[]>) =>
    sectionHref(store.id, segment, store.permissions, query);

  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
      <KpiCard
        label="Active exceptions"
        value={formatQuantity(active.total)}
        secondary={`${formatQuantity(active.by_band.P1 ?? 0)} P1 · ${formatQuantity(active.by_band.P2 ?? 0)} P2`}
        href={href("exceptions", { view: "active" })}
      />
      <KpiCard
        label="Unassigned"
        value={formatQuantity(active.unassigned)}
        secondary={unassignedP1.data !== undefined ? `${formatQuantity(unassignedP1.data)} ${unassignedP1.data === 1 ? "is" : "are"} P1` : undefined}
        href={href("exceptions", { view: "unassigned" })}
      />
      <KpiCard
        label="Past due exceptions"
        value={formatQuantity(active.past_due)}
        secondary="Due date passed"
        href={href("exceptions", { view: "active", due: "overdue", sort: "due_at" })}
      />
      <KpiCard
        label="Overdue orders"
        value={formatQuantity(orders.overdue_count)}
        secondary={
          <>
            <Money value={orders.overdue_value} /> gross value
          </>
        }
        href={href("orders", { overdue: "true", sort: "ship_by" })}
        info="Paid orders still unshipped after their ship-by deadline (BR-202)."
      />
      <KpiCard
        label="Awaiting shipment"
        value={formatQuantity(orders.awaiting_shipment)}
        secondary="Paid, not shipped"
        href={href("orders", { status: ["PAID", "PROCESSING", "READY_TO_SHIP"] })}
      />
      <KpiCard
        label="On-time shipments, 30 days"
        value={onTime.on_time_rate_pct === null ? <NoValue /> : formatPercentValue(onTime.on_time_rate_pct)}
        secondary={
          onTime.on_time_rate_pct === null
            ? "No shipments with a deadline in the last 30 days"
            : `${formatQuantity(onTime.on_time)} of ${formatQuantity(onTime.shipped_with_deadline)} on time`
        }
        info="Shipped in the window with a ship-by date. On time means shipped_at ≤ ship_by."
      />
    </div>
  );
}

function AttentionRow({ item, href }: { item: AttentionItem; href?: string }) {
  return (
    <li className="relative flex flex-col gap-1 border-b px-4 py-3 last:border-b-0 hover:bg-surface-hover md:px-5">
      <div className="flex flex-wrap items-center gap-2">
        <PriorityIndicator band={item.priority_band} score={item.priority_score} />
        <SeverityBadge severity={item.severity} />
        {href ? (
          <Link
            href={href}
            aria-label={`${item.reference}, ${item.title}`}
            className="min-w-0 flex-1 basis-60 text-body-strong outline-offset-[-2px] after:absolute after:inset-0 hover:underline"
          >
            {item.title}
          </Link>
        ) : (
          <span className="min-w-0 flex-1 basis-60 text-body-strong">{item.title}</span>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted-foreground">
        <span className="font-medium text-foreground">{item.reference}</span>
        <span aria-hidden>·</span>
        <DueLabel dueAt={item.due_at} />
        <span aria-hidden>·</span>
        <span>{item.assignee_name ?? "Unassigned"}</span>
        {item.status !== "OPEN" ? <ExceptionStatusPill status={item.status} /> : null}
      </div>
    </li>
  );
}

/** The top active exceptions by priority (S-02 "Needs attention"). */
export function AttentionList({ dashboard }: { dashboard: Dashboard }) {
  const store = useStore();
  const triage = useExceptionCount({ status: ["OPEN", "REOPENED"] });
  const triageHref = sectionHref(store.id, "exceptions", store.permissions, { view: "triage" });
  const allHref = sectionHref(store.id, "exceptions", store.permissions, { view: "active" });
  const lastRun = dashboard.data_freshness.last_evaluation_run;

  return (
    <section aria-labelledby="attention-title" className="rounded-lg border bg-card">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b px-4 py-3 md:px-5">
        <h2 id="attention-title" className="text-title-sm">
          Needs attention
        </h2>
        {triage.data !== undefined ? (
          <MaybeLink href={triageHref} className="text-sm">
            {triageHref ? `Open triage queue (${formatQuantity(triage.data)})` : `${formatQuantity(triage.data)} awaiting triage`}
          </MaybeLink>
        ) : null}
      </div>
      {dashboard.attention.length === 0 ? (
        <EmptyState
          icon={CircleCheck}
          variant="success"
          title="Nothing needs attention"
          description={
            lastRun
              ? `The last evaluation at ${formatDateTimeCompact(lastRun.started_at, store.timezone)} found no active exceptions.`
              : "No active exceptions."
          }
        />
      ) : (
        <>
          <ol aria-label="Active exceptions by priority">
            {dashboard.attention.map((item) => (
              <AttentionRow
                key={item.id}
                item={item}
                href={allHref ? `/s/${store.id}/exceptions/${item.id}` : undefined}
              />
            ))}
          </ol>
          {allHref ? (
            <div className="border-t px-4 py-3 text-right text-sm md:px-5">
              <Link href={allHref} className="text-link hover:underline">
                View all active ({formatQuantity(dashboard.active_exceptions.total)})
              </Link>
            </div>
          ) : null}
        </>
      )}
    </section>
  );
}

const CATEGORIES: ExceptionCategory[] = ["INVENTORY", "FULFILLMENT", "PAYMENT", "DATA_QUALITY"];

/**
 * Active exceptions and order value at risk per category. Value at risk is never totalled: one
 * order can appear in several exceptions (S-02, BR-404). Data-quality findings claim no exposure
 * (EXCEPTION_CATALOG), so that cell is "—".
 */
export function CategoryCard({ dashboard }: { dashboard: Dashboard }) {
  const store = useStore();
  const { by_category: counts, exposure_by_category: exposure } = dashboard.active_exceptions;

  return (
    <section aria-labelledby="category-title" className="rounded-lg border bg-card p-4 md:p-5">
      <h2 id="category-title" className="text-title-sm">
        Active exceptions by category
      </h2>
      <table className="mt-3 w-full text-body">
        <thead>
          <tr className="text-xs text-muted-foreground">
            <th scope="col" className="pb-2 text-left font-medium">
              Category
            </th>
            <th scope="col" className="pb-2 text-right font-medium">
              Count
            </th>
            <th scope="col" className="pb-2 text-right font-medium">
              Value at risk
            </th>
          </tr>
        </thead>
        <tbody>
          {CATEGORIES.map((category) => (
            <tr key={category} className="border-t">
              <th scope="row" className="py-2 text-left font-normal">
                <MaybeLink
                  href={sectionHref(store.id, "exceptions", store.permissions, { view: "active", category })}
                >
                  {categoryLabels[category]}
                </MaybeLink>
              </th>
              <td className="py-2 text-right tabular-nums">{formatQuantity(counts[category] ?? 0)}</td>
              <td className="py-2 text-right">
                {category === "DATA_QUALITY" ? <NoValue /> : <Money value={exposure[category] ?? "0"} />}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-3 text-xs font-normal text-muted-foreground">
        Order value at risk (gross, per category). An order can count in more than one category. Not a measure of
        loss.
      </p>
    </section>
  );
}

const HEALTH_ROWS: Array<{ health: StockHealth; key: keyof Dashboard["inventory"] }> = [
  { health: "OVERSOLD", key: "oversold" },
  { health: "OUT_OF_STOCK", key: "out_of_stock" },
  { health: "BELOW_REORDER_POINT", key: "below_reorder_point" },
  { health: "APPROACHING_REORDER_POINT", key: "approaching_reorder_point" },
  { health: "HEALTHY", key: "healthy" },
];

const healthIconTone: Record<StockHealth, string> = {
  OVERSOLD: "text-tone-danger-fg",
  OUT_OF_STOCK: "text-tone-danger-fg",
  BELOW_REORDER_POINT: "text-tone-warning-fg",
  APPROACHING_REORDER_POINT: "text-tone-caution-fg",
  HEALTHY: "text-tone-success-fg",
};

/** Active products by stock health from current balances (S-02 "Stock health"). */
export function StockHealthCard({ dashboard }: { dashboard: Dashboard }) {
  const store = useStore();
  return (
    <section aria-labelledby="health-title" className="rounded-lg border bg-card p-4 md:p-5">
      <h2 id="health-title" className="text-title-sm">
        Stock health
      </h2>
      <p className="text-sm text-muted-foreground">
        {formatQuantity(dashboard.inventory.active_products)} active products
      </p>
      <ul className="mt-3 flex flex-col">
        {HEALTH_ROWS.map(({ health, key }) => {
          const meta = stockHealthMeta[health];
          const Icon = meta.icon;
          return (
            <li key={health} className="flex items-center gap-2 border-t py-2 text-body">
              <Icon aria-hidden className={cn("size-4 shrink-0", healthIconTone[health])} />
              <MaybeLink
                href={sectionHref(store.id, "inventory", store.permissions, { health })}
                className="flex-1"
              >
                {meta.label}
              </MaybeLink>
              <span className="tabular-nums">{formatQuantity(dashboard.inventory[key])}</span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
