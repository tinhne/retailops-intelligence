"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ArrowLeftRight, SearchX } from "lucide-react";
import Link from "next/link";

import { DataTable, type Column } from "@/components/data/data-table";
import { FilterChips, MultiSelectFilter, Pagination, SelectField, type Chip, type Option } from "@/components/data/list-controls";
import { NoValue } from "@/components/data/values";
import { sectionHref } from "@/components/shell/nav-config";
import { PageHeader } from "@/components/shell/page-header";
import { EmptyState } from "@/components/states/empty-state";
import { PermissionDenied } from "@/components/states/permission-denied";
import { Button } from "@/components/ui/button";
import { ImportLink } from "@/features/imports/import-actions";
import { exceptionKeys, exceptionsApi } from "@/lib/api/exceptions-api";
import { inventoryApi, inventoryKeys, type Movement } from "@/lib/api/inventory-api";
import { formatDateTimeShort, storeMidnight, zoneGenericName } from "@/lib/format/datetime";
import { formatCount, formatDelta, formatQuantity } from "@/lib/format/number";
import { useDocumentTitle } from "@/lib/hooks/use-document-title";
import { useListState } from "@/lib/hooks/use-list-state";
import { useNow } from "@/lib/hooks/use-now";
import { defineListParams } from "@/lib/list-params";
import { movementSourceLabels, movementTypeLabels, type MovementSource, type MovementType } from "@/lib/status-maps";
import { useStore } from "@/lib/store/store-context";
import { cn } from "@/lib/utils";

const TYPES = Object.keys(movementTypeLabels) as MovementType[];
const SOURCES = Object.keys(movementSourceLabels) as MovementSource[];
const OCCURRED = ["today", "7d", "30d", "90d"] as const;
type Occurred = (typeof OCCURRED)[number];
const OCCURRED_LABELS: Record<Occurred, string> = { today: "Today", "7d": "Last 7 days", "30d": "Last 30 days", "90d": "Last 90 days" };
const OCCURRED_DAYS: Record<Occurred, number> = { today: 0, "7d": 6, "30d": 29, "90d": 89 };
const SHIPMENT_REFERENCE = "order_item:";

export const movementsList = defineListParams(
  {
    product_id: { kind: "id" },
    movement_type: { kind: "many", values: TYPES },
    source: { kind: "one", values: SOURCES },
    occurred: { kind: "one", values: OCCURRED },
  },
  { sorts: ["-occurred_at", "occurred_at", "-recorded_at"], defaultSort: "-occurred_at", pageSizes: [50, 100], defaultPageSize: 50 },
);

const SORT_OPTIONS: Option[] = [
  { value: "-occurred_at", label: "Occurred, newest" },
  { value: "occurred_at", label: "Occurred, oldest" },
  { value: "-recorded_at", label: "Recorded, newest" },
];

/** Shipments reference the order line and carry the order number as their note (BR-131). */
const isShipmentNote = (movement: Movement) => Boolean(movement.reference?.startsWith(SHIPMENT_REFERENCE) && movement.note?.startsWith("Order "));

function Delta({ value }: { value: number }) {
  return <span className={cn(value === 0 ? "text-muted-foreground" : value < 0 && "text-tone-danger-fg")}>{formatDelta(value)}</span>;
}

/** The append-only stock ledger (SCREEN_SPECIFICATIONS S-10). */
export function MovementsScreen() {
  const store = useStore();
  const now = useNow();
  useDocumentTitle("Movements");
  const canRead = store.permissions.has("inventory.read");
  const canSeeProducts = store.permissions.has("catalog.read");
  const { params, update, clearAll, isFiltered } = useListState(movementsList);
  const zone = zoneGenericName(store.timezone);

  const occurred = params.occurred as Occurred | null;
  const query = {
    product_id: params.product_id ?? undefined,
    movement_type: params.movement_type,
    source: params.source ?? undefined,
    from: occurred ? storeMidnight(now, store.timezone, OCCURRED_DAYS[occurred]).toISOString() : undefined,
    sort: params.sort,
    page: params.page,
    page_size: params.page_size,
  };
  const list = useQuery({
    queryKey: inventoryKeys.movements(store.id, query),
    queryFn: ({ signal }) => inventoryApi.movements(store.id, query, signal),
    placeholderData: keepPreviousData,
    enabled: canRead,
  });
  // The chip names the product; the ledger rows carry the SKU too, for people without catalog access.
  // Names for "Recorded by". The member list is readable with exceptions.read.
  const members = useQuery({
    queryKey: exceptionKeys.members(store.id),
    queryFn: ({ signal }) => exceptionsApi.members(store.id, signal),
    enabled: canRead && store.permissions.has("exceptions.read"),
    staleTime: 5 * 60_000,
  });
  const product = useQuery({
    queryKey: inventoryKeys.product(store.id, params.product_id ?? ""),
    queryFn: ({ signal }) => inventoryApi.product(store.id, params.product_id ?? "", signal),
    enabled: canRead && canSeeProducts && params.product_id !== null,
    staleTime: 5 * 60_000,
  });

  if (!canRead) return <PermissionDenied pageName="movements" permission="inventory.read" />;

  const productLabel = product.data?.sku ?? list.data?.items[0]?.sku ?? "Selected product";
  const chips: Chip[] = [
    ...(params.product_id ? [{ key: "product", label: `Product: ${productLabel}`, onRemove: () => update({ product_id: null }) }] : []),
    ...(params.movement_type.length
      ? [{ key: "type", label: `Type: ${params.movement_type.map((t) => movementTypeLabels[t as MovementType]).join(", ")}`, onRemove: () => update({ movement_type: [] }) }]
      : []),
    ...(params.source ? [{ key: "source", label: `Source: ${movementSourceLabels[params.source as MovementSource]}`, onRemove: () => update({ source: null }) }] : []),
    ...(occurred ? [{ key: "occurred", label: `Occurred: ${OCCURRED_LABELS[occurred]}`, onRemove: () => update({ occurred: null }) }] : []),
  ];

  const reference = (movement: Movement) => {
    if (!movement.reference) return <NoValue />;
    if (isShipmentNote(movement) && movement.note) {
      const orderNumber = movement.note.slice("Order ".length);
      const href = sectionHref(store.id, "orders", store.permissions, { q: orderNumber });
      return href ? (
        <Link href={href} className="whitespace-nowrap hover:underline">
          {movement.note}
        </Link>
      ) : (
        <span className="whitespace-nowrap">{movement.note}</span>
      );
    }
    return <span className="font-mono text-xs break-all">{movement.reference}</span>;
  };

  const columns: Column<Movement>[] = [
    {
      id: "occurred",
      header: `Occurred (${zone})`,
      pinned: true,
      cell: (m) => (
        <time dateTime={m.occurred_at} className="whitespace-nowrap">
          {formatDateTimeShort(m.occurred_at, store.timezone, now)}
        </time>
      ),
    },
    {
      id: "sku",
      header: "SKU",
      cell: (m) =>
        canSeeProducts ? (
          <Link href={`/s/${store.id}/products/${m.product_id}`} className="font-medium whitespace-nowrap hover:underline">
            {m.sku}
          </Link>
        ) : (
          <span className="font-medium whitespace-nowrap">{m.sku}</span>
        ),
    },
    { id: "type", header: "Type", cell: (m) => <span className="whitespace-nowrap">{movementTypeLabels[m.movement_type]}</span> },
    { id: "on_hand", header: "On hand Δ", align: "right", cell: (m) => <Delta value={m.on_hand_delta} /> },
    { id: "on_hand_after", header: "On hand after", align: "right", hideBelow: "md", cell: (m) => formatQuantity(m.on_hand_after) },
    { id: "incoming", header: "Incoming Δ", align: "right", hideBelow: "md", cell: (m) => <Delta value={m.incoming_delta} /> },
    { id: "source", header: "Source", hideBelow: "lg", cell: (m) => movementSourceLabels[m.source] },
    { id: "reference", header: "Reference", hideBelow: "md", cell: reference },
    {
      id: "note",
      header: "Note",
      hideBelow: "xl",
      cell: (m) =>
        m.note && !isShipmentNote(m) ? (
          <span className="line-clamp-1 max-w-64" title={m.note}>
            {m.note}
          </span>
        ) : (
          <NoValue />
        ),
    },
    {
      id: "recorded_by",
      header: "Recorded by",
      hideBelow: "xl",
      cell: (m) =>
        m.created_by === null ? (
          "System"
        ) : members.data ? (
          (members.data.items.find((member) => member.id === m.created_by)?.full_name ?? "Former member")
        ) : (
          <NoValue />
        ),
    },
    {
      id: "recorded",
      header: `Recorded (${zone})`,
      hideBelow: "2xl",
      cell: (m) => (
        <time dateTime={m.recorded_at} className="whitespace-nowrap text-muted-foreground">
          {formatDateTimeShort(m.recorded_at, store.timezone, now)}
        </time>
      ),
    },
  ];

  const total = list.data?.total ?? 0;
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Movements" subtitle="Append-only ledger. Corrections appear as Correction entries." />
      <section aria-label="Movement ledger" className="rounded-lg border bg-card">
        <div className="flex flex-col gap-3 border-b p-4">
          <div className="flex flex-wrap items-center gap-3">
            <MultiSelectFilter
              label="Type"
              options={TYPES.map((type) => ({ value: type, label: movementTypeLabels[type] }))}
              selected={params.movement_type}
              onChange={(movement_type) => update({ movement_type })}
            />
            <SelectField
              label="Source"
              value={params.source ?? ""}
              options={[{ value: "", label: "Any" }, ...SOURCES.map((source) => ({ value: source, label: movementSourceLabels[source] }))]}
              onChange={(value) => update({ source: value || null })}
            />
            <SelectField
              label="Occurred"
              value={occurred ?? ""}
              options={[{ value: "", label: "Any time" }, ...OCCURRED.map((value) => ({ value, label: OCCURRED_LABELS[value] }))]}
              onChange={(value) => update({ occurred: value || null })}
            />
            <SelectField label="Sort" value={params.sort} options={SORT_OPTIONS} onChange={(sort) => update({ sort })} />
            <p className="ml-auto text-sm text-muted-foreground" aria-live="polite">
              {list.data ? formatCount(total, "movement") : null}
            </p>
          </div>
          <FilterChips chips={chips} onClearAll={clearAll} />
        </div>
        <DataTable
          caption={`Movements, page ${params.page}, sorted by ${SORT_OPTIONS.find((o) => o.value === params.sort)?.label ?? "occurred, newest"}`}
          columns={columns}
          rows={list.data?.items}
          getRowId={(m) => m.id}
          status={list.isPending ? "loading" : list.isError ? "error" : "success"}
          isFetching={list.isPlaceholderData}
          error={list.error}
          onRetry={() => void list.refetch()}
          errorTitle="Couldn't load movements"
          isFiltered={isFiltered}
          density="compact"
          noResults={
            <EmptyState
              icon={SearchX}
              title="No movements match these filters"
              action={
                <Button type="button" variant="secondary" onClick={clearAll}>
                  Clear filters
                </Button>
              }
            />
          }
          empty={
            <EmptyState
              icon={ArrowLeftRight}
              title="No movements yet"
              description="Inventory adjustment imports and shipped orders write ledger entries."
              action={<ImportLink type="inventory_adjustments" label="Import inventory adjustments" />}
            />
          }
        />
        {list.data && total > 0 ? (
          <Pagination page={params.page} pageSize={params.page_size} total={total} onPageChange={(page) => update({ page }, "push")} onPageSizeChange={(page_size) => update({ page_size })} pageSizes={movementsList.options.pageSizes} />
        ) : null}
      </section>
    </div>
  );
}
