"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Boxes, CircleCheck, SearchX } from "lucide-react";
import Link from "next/link";

import { DataTable, type Column } from "@/components/data/data-table";
import { FilterChips, MultiSelectFilter, Pagination, SearchInput, SelectField, type Chip } from "@/components/data/list-controls";
import { NoValue } from "@/components/data/values";
import { PageHeader } from "@/components/shell/page-header";
import { EmptyState } from "@/components/states/empty-state";
import { PermissionDenied } from "@/components/states/permission-denied";
import { HealthBadge } from "@/components/status/status-pill";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import type { InventoryPosition } from "@/lib/api/orders-api";
import { inventoryApi, inventoryKeys } from "@/lib/api/inventory-api";
import { storeApi, storeKeys } from "@/lib/api/store-api";
import { formatDate, formatDateTimeShort, zoneGenericName } from "@/lib/format/datetime";
import { formatCount, formatQuantity } from "@/lib/format/number";
import { useDocumentTitle } from "@/lib/hooks/use-document-title";
import { useListState } from "@/lib/hooks/use-list-state";
import { defineListParams } from "@/lib/list-params";
import { displayHealth, stockHealthMeta, type StockHealth } from "@/lib/status-maps";
import { useStore } from "@/lib/store/store-context";
import { cn } from "@/lib/utils";

const HEALTH: StockHealth[] = ["OVERSOLD", "OUT_OF_STOCK", "BELOW_REORDER_POINT", "APPROACHING_REORDER_POINT", "HEALTHY"];
const SUMMARY_KEYS: Record<StockHealth, "oversold" | "out_of_stock" | "below_reorder_point" | "approaching_reorder_point" | "healthy"> = {
  OVERSOLD: "oversold",
  OUT_OF_STOCK: "out_of_stock",
  BELOW_REORDER_POINT: "below_reorder_point",
  APPROACHING_REORDER_POINT: "approaching_reorder_point",
  HEALTHY: "healthy",
};

export const positionsList = defineListParams(
  {
    q: { kind: "text", max: 100 },
    health: { kind: "many", values: HEALTH },
    category: { kind: "text", max: 100 },
    include_inactive: { kind: "flag" },
  },
  { sorts: ["available", "days_of_cover", "sku"], defaultSort: "available", pageSizes: [50, 100], defaultPageSize: 50 },
);

const SORT_OPTIONS = [
  { value: "available", label: "Available, lowest" },
  { value: "days_of_cover", label: "Days of cover, lowest" },
  { value: "sku", label: "SKU" },
];

const oneDecimal = (value: string | null) => (value === null ? null : Number(value).toFixed(1));

/** Stock risk across every SKU, ranked by availability (SCREEN_SPECIFICATIONS S-09). */
export function PositionsScreen() {
  const store = useStore();
  useDocumentTitle("Inventory");
  const canRead = store.permissions.has("inventory.read");
  const { params, update, clearAll, isFiltered } = useListState(positionsList);
  const zone = zoneGenericName(store.timezone);

  const query = {
    q: params.q.trim() || undefined,
    health: params.health,
    category: params.category || undefined,
    include_inactive: params.include_inactive || undefined,
    sort: params.sort,
    page: params.page,
    page_size: params.page_size,
  };
  const list = useQuery({
    queryKey: inventoryKeys.positions(store.id, query),
    queryFn: ({ signal }) => inventoryApi.positions(store.id, query, signal),
    placeholderData: keepPreviousData,
    enabled: canRead,
  });
  const dashboard = useQuery({
    queryKey: storeKeys.dashboard(store.id),
    queryFn: ({ signal }) => storeApi.dashboard(store.id, signal),
    enabled: canRead && store.permissions.has("dashboard.read"),
  });
  const categories = useQuery({
    queryKey: inventoryKeys.categories(store.id),
    queryFn: ({ signal }) => inventoryApi.categories(store.id, signal),
    enabled: canRead && store.permissions.has("catalog.read"),
    staleTime: 5 * 60_000,
  });

  if (!canRead) return <PermissionDenied pageName="inventory" permission="inventory.read" />;

  const productHref = (position: InventoryPosition) => `/s/${store.id}/products/${position.product_id}`;
  const linkProducts = store.permissions.has("catalog.read");
  const toggleHealth = (health: StockHealth) =>
    update({ health: params.health.includes(health) ? params.health.filter((h) => h !== health) : [...params.health, health] });
  const chips: Chip[] = [
    ...(params.q ? [{ key: "q", label: `Search: ${params.q}`, onRemove: () => update({ q: "" }) }] : []),
    ...(params.health.length
      ? [{ key: "health", label: `Health: ${params.health.map((h) => stockHealthMeta[h as StockHealth].label).join(", ")}`, onRemove: () => update({ health: [] }) }]
      : []),
    ...(params.category ? [{ key: "category", label: `Category: ${params.category}`, onRemove: () => update({ category: "" }) }] : []),
    ...(params.include_inactive ? [{ key: "inactive", label: "Including inactive products", onRemove: () => update({ include_inactive: false }) }] : []),
  ];

  const sku = (position: InventoryPosition) =>
    linkProducts ? (
      <Link href={productHref(position)} className="font-medium whitespace-nowrap outline-offset-[-2px] after:absolute after:inset-0 hover:underline">
        {position.sku}
      </Link>
    ) : (
      <span className="font-medium">{position.sku}</span>
    );
  const columns: Column<InventoryPosition>[] = [
    { id: "sku", header: "SKU", cell: sku },
    { id: "name", header: "Product", hideBelow: "md", cell: (p) => <span className="line-clamp-2 min-w-40">{p.name}</span> },
    { id: "health", header: "Health", cell: (p) => <HealthBadge health={p.health} onHand={p.on_hand} /> },
    { id: "on_hand", header: "On hand", align: "right", hideBelow: "md", cell: (p) => <span className={cn(p.on_hand < 0 && "text-tone-danger-fg")}>{formatQuantity(p.on_hand)}</span> },
    { id: "reserved", header: "Reserved", align: "right", hideBelow: "md", cell: (p) => formatQuantity(p.reserved) },
    { id: "available", header: "Available", align: "right", cell: (p) => <span className={cn("font-medium", p.available < 0 && "text-tone-danger-fg")}>{formatQuantity(p.available)}</span> },
    {
      id: "incoming",
      header: "Incoming",
      align: "right",
      hideBelow: "lg",
      cell: (p) => (
        <span className="whitespace-nowrap">
          {formatQuantity(p.incoming)}
          {p.incoming_eta ? <span className="text-muted-foreground"> · ETA {formatDate(p.incoming_eta, store.timezone).replace(/, \d{4}$/, "")}</span> : null}
        </span>
      ),
    },
    { id: "reorder", header: "Reorder point", align: "right", hideBelow: "lg", cell: (p) => formatQuantity(p.reorder_point) },
    { id: "avg", header: "Avg daily units (est.)", align: "right", hideBelow: "2xl", cell: (p) => oneDecimal(p.avg_daily_units) ?? <NoValue /> },
    {
      id: "cover",
      header: "Days of cover (est.)",
      align: "right",
      hideBelow: "lg",
      cell: (p) =>
        displayHealth(p.health, p.on_hand) === "DATA_ISSUE" ? (
          <NoValue />
        ) : p.days_of_cover === null ? (
          <span title="Not enough sales history" className="text-muted-foreground">—</span>
        ) : (
          oneDecimal(p.days_of_cover)
        ),
    },
    {
      id: "count",
      header: `Last count (${zone})`,
      hideBelow: "xl",
      cell: (p) => (p.last_cycle_count_at ? <span className="whitespace-nowrap">{formatDateTimeShort(p.last_cycle_count_at, store.timezone)}</span> : <NoValue />),
    },
  ];

  const total = list.data?.total ?? 0;
  const summary = dashboard.data?.inventory;
  const onlyOversold = params.health.length === 1 && params.health[0] === "OVERSOLD" && chips.length === 1;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Inventory" />
      {store.permissions.has("dashboard.read") ? (
        <div role="group" aria-label="Filter by stock health" className="-mx-(--page-gutter) flex gap-2 overflow-x-auto px-(--page-gutter) pb-1">
          {dashboard.isPending
            ? HEALTH.map((h) => <Skeleton key={h} className="h-8 w-32 shrink-0" />)
            : summary
              ? HEALTH.map((h) => {
                  const pressed = params.health.includes(h);
                  const Icon = stockHealthMeta[h].icon;
                  return (
                    <Button key={h} type="button" variant="secondary" size="sm" aria-pressed={pressed} onClick={() => toggleHealth(h)} className={cn("shrink-0", pressed && "border-primary bg-surface-selected")}>
                      <Icon aria-hidden />
                      {stockHealthMeta[h].label}{" "}
                      <span className="tabular-nums text-muted-foreground">{formatQuantity(summary[SUMMARY_KEYS[h]])}</span>
                    </Button>
                  );
                })
              : null}
        </div>
      ) : null}
      <p className="-mt-3 text-sm text-muted-foreground">
        Available = on hand − reserved. Incoming stock is shown separately and never counted as available (BR-101, BR-103).
      </p>
      <section aria-label="Inventory positions" className="rounded-lg border bg-card">
        <div className="flex flex-col gap-3 border-b p-4">
          <div className="flex flex-wrap items-center gap-2">
            <SearchInput label="Search inventory" placeholder="SKU or name" value={params.q} onChange={(q) => update({ q })} />
            <MultiSelectFilter label="Health" options={HEALTH.map((h) => ({ value: h, label: stockHealthMeta[h].label }))} selected={params.health} onChange={(health) => update({ health })} />
            <label className="ml-1 flex h-8 cursor-pointer items-center gap-2 text-body">
              <Checkbox checked={params.include_inactive} onCheckedChange={(checked) => update({ include_inactive: checked === true })} />
              Include inactive products
            </label>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <SelectField
              label="Category"
              value={params.category}
              options={[{ value: "", label: "Any" }, ...(categories.data?.items ?? []).map((category) => ({ value: category, label: category }))]}
              onChange={(category) => update({ category })}
            />
            <SelectField label="Sort" value={params.sort} options={SORT_OPTIONS} onChange={(sort) => update({ sort })} />
            <p className="ml-auto text-sm text-muted-foreground" aria-live="polite">
              {list.data ? formatCount(total, "product") : null}
            </p>
          </div>
          <FilterChips chips={chips} onClearAll={clearAll} />
        </div>
        <DataTable
          caption={`Inventory positions, page ${params.page}, sorted by ${SORT_OPTIONS.find((o) => o.value === params.sort)?.label ?? "available"}`}
          columns={columns}
          rows={list.data?.items}
          getRowId={(p) => p.product_id}
          status={list.isPending ? "loading" : list.isError ? "error" : "success"}
          isFetching={list.isPlaceholderData}
          error={list.error}
          onRetry={() => void list.refetch()}
          errorTitle="Couldn't load inventory"
          isFiltered={isFiltered}
          density="compact"
          renderStackedRow={(p) => (
            <div className="flex flex-col gap-1 p-4">
              <div className="flex items-center gap-2">
                {sku(p)}
                <HealthBadge health={p.health} onHand={p.on_hand} />
              </div>
              <p className="text-body">{p.name}</p>
              <p className="text-sm text-muted-foreground">
                <span className={cn(p.available < 0 && "text-tone-danger-fg")}>Available {formatQuantity(p.available)}</span> · On hand{" "}
                {formatQuantity(p.on_hand)} · Incoming {formatQuantity(p.incoming)}
                {p.incoming_eta ? ` (${formatDate(p.incoming_eta, store.timezone).replace(/, \d{4}$/, "")})` : ""}
              </p>
            </div>
          )}
          noResults={
            onlyOversold ? (
              <EmptyState icon={CircleCheck} variant="success" title="No oversold products" />
            ) : (
              <EmptyState
                icon={SearchX}
                title="No products match these filters"
                action={
                  <Button type="button" variant="secondary" onClick={clearAll}>
                    Clear filters
                  </Button>
                }
              />
            )
          }
          empty={<EmptyState icon={Boxes} title="No stock positions yet" description="Import products, then inventory adjustments (a CYCLE_COUNT sets on-hand)." />}
        />
        {list.data && total > 0 ? (
          <Pagination page={params.page} pageSize={params.page_size} total={total} onPageChange={(page) => update({ page }, "push")} onPageSizeChange={(page_size) => update({ page_size })} />
        ) : null}
      </section>
    </div>
  );
}
