"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { AlarmClock, CircleCheck, SearchX, ShoppingCart } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef } from "react";
import { toast } from "sonner";

import { DataTable, type Column } from "@/components/data/data-table";
import { FilterChips, MultiSelectFilter, Pagination, SearchInput, SelectField, type Chip, type Option } from "@/components/data/list-controls";
import { Money } from "@/components/data/values";
import { PageHeader } from "@/components/shell/page-header";
import { EmptyState } from "@/components/states/empty-state";
import { PermissionDenied } from "@/components/states/permission-denied";
import { AxisText, OrderStatusPill } from "@/components/status/status-pill";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { ImportLink } from "@/features/imports/import-actions";
import { ordersApi, orderKeys, type OrderListItem } from "@/lib/api/orders-api";
import { formatDateTimeShort, formatDue, zoneGenericName } from "@/lib/format/datetime";
import { formatCount, formatQuantity } from "@/lib/format/number";
import { useDocumentTitle } from "@/lib/hooks/use-document-title";
import { useNow } from "@/lib/hooks/use-now";
import { channelLabels, fulfillmentStatusMeta, orderStatusMeta, paymentStatusMeta } from "@/lib/status-maps";
import { useStore } from "@/lib/store/store-context";

import {
  CHANNELS,
  FULFILLMENT_STATUSES,
  isOrderFiltered,
  ORDER_STATUSES,
  parseOrderParams,
  PAYMENT_STATUSES,
  serializeOrderParams,
  STATUS_GROUPS,
  toOrderQuery,
  updateOrderParams,
  type OrderParams,
} from "./order-params";

const PLACED_LABELS = { today: "Today", "7d": "Last 7 days", "30d": "Last 30 days", "60d": "Last 60 days" } as const;
const SORT_OPTIONS: Option[] = [
  { value: "-placed_at", label: "Placed, newest" },
  { value: "placed_at", label: "Placed, oldest" },
  { value: "ship_by", label: "Ship by, soonest" },
  { value: "-total", label: "Total, highest" },
  { value: "order_number", label: "Order number" },
];

/** "Overdue 30h" when an order missed its ship-by deadline (BR-202). */
function OverdueFlag({ order, now }: { order: Pick<OrderListItem, "is_overdue" | "ship_by">; now: Date }) {
  if (!order.is_overdue || !order.ship_by) return null;
  return (
    <span className="inline-flex items-center gap-1 whitespace-nowrap text-overdue">
      <AlarmClock aria-hidden className="size-3.5" />
      {formatDue(order.ship_by, now).text}
    </span>
  );
}

/** Read-only order list (SCREEN_SPECIFICATIONS S-05). */
export function OrdersScreen() {
  const store = useStore();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const now = useNow();
  useDocumentTitle("Orders");
  const canRead = store.permissions.has("orders.read");
  const zone = zoneGenericName(store.timezone);

  const { params, invalid } = useMemo(() => parseOrderParams(searchParams), [searchParams]);
  const navigate = useCallback(
    (next: OrderParams, mode: "replace" | "push" = "replace") => {
      const search = serializeOrderParams(next).toString();
      const url = search ? `${pathname}?${search}` : pathname;
      if (mode === "push") router.push(url, { scroll: false });
      else router.replace(url, { scroll: false });
    },
    [pathname, router],
  );
  const update = (patch: Partial<OrderParams>, mode: "replace" | "push" = "replace") => navigate(updateOrderParams(params, patch), mode);

  const normalised = useRef(false);
  useEffect(() => {
    if (normalised.current || invalid.length === 0) return;
    normalised.current = true;
    toast.info("Some filters in the link weren't recognised and were removed.");
    navigate(params);
  }, [invalid.length, navigate, params]);

  const minute = Math.floor(now.getTime() / 60_000);
  const query = useMemo(() => toOrderQuery(params, new Date(minute * 60_000), store.timezone), [params, minute, store.timezone]);
  const list = useQuery({
    queryKey: orderKeys.list(store.id, query),
    queryFn: ({ signal }) => ordersApi.list(store.id, query, signal),
    placeholderData: keepPreviousData,
    enabled: canRead,
  });

  if (!canRead) return <PermissionDenied pageName="orders" permission="orders.read" />;

  const hrefFor = (order: OrderListItem) => `/s/${store.id}/orders/${order.id}`;
  const clearAll = () =>
    update({ q: "", status: [], payment_status: null, fulfillment_status: null, channel: null, placed: null, overdue: false });
  const chips: Chip[] = [
    ...(params.q ? [{ key: "q", label: `Search: ${params.q}`, onRemove: () => update({ q: "" }) }] : []),
    ...(params.status.length
      ? [{ key: "status", label: `Status: ${params.status.map((s) => orderStatusMeta[s].label).join(", ")}`, onRemove: () => update({ status: [] }) }]
      : []),
    ...(params.payment_status ? [{ key: "payment", label: `Payment: ${paymentStatusMeta[params.payment_status].label}`, onRemove: () => update({ payment_status: null }) }] : []),
    ...(params.fulfillment_status
      ? [{ key: "fulfillment", label: `Fulfillment: ${fulfillmentStatusMeta[params.fulfillment_status].label}`, onRemove: () => update({ fulfillment_status: null }) }]
      : []),
    ...(params.channel ? [{ key: "channel", label: `Channel: ${channelLabels[params.channel]}`, onRemove: () => update({ channel: null }) }] : []),
    ...(params.placed ? [{ key: "placed", label: `Placed: ${PLACED_LABELS[params.placed]}`, onRemove: () => update({ placed: null }) }] : []),
    ...(params.overdue ? [{ key: "overdue", label: "Overdue only", onRemove: () => update({ overdue: false }) }] : []),
  ];

  const columns: Column<OrderListItem>[] = [
    {
      id: "order",
      header: "Order",
      cell: (order) => (
        <Link href={hrefFor(order)} className="text-body-strong outline-offset-[-2px] after:absolute after:inset-0 hover:underline">
          {order.order_number}
        </Link>
      ),
    },
    {
      id: "placed",
      header: `Placed (${zone})`,
      cell: (order) => (
        <time dateTime={order.placed_at} className="whitespace-nowrap">
          {formatDateTimeShort(order.placed_at, store.timezone, now)}
        </time>
      ),
    },
    { id: "channel", header: "Channel", hideBelow: "lg", cell: (order) => channelLabels[order.channel] },
    { id: "status", header: "Status", cell: (order) => <OrderStatusPill status={order.status} /> },
    { id: "payment", header: "Payment", hideBelow: "md", cell: (order) => <AxisText axis="payment" value={order.payment_status} /> },
    { id: "fulfillment", header: "Fulfillment", hideBelow: "lg", cell: (order) => <AxisText axis="fulfillment" value={order.fulfillment_status} /> },
    {
      id: "ship_by",
      header: `Ship by (${zone})`,
      hideBelow: "md",
      cell: (order) =>
        order.ship_by ? (
          <span className="flex flex-col">
            <time dateTime={order.ship_by} className="whitespace-nowrap">
              {formatDateTimeShort(order.ship_by, store.timezone, now)}
            </time>
            <OverdueFlag order={order} now={now} />
          </span>
        ) : (
          <span className="text-muted-foreground">—</span>
        ),
    },
    { id: "lines", header: "Lines", align: "right", hideBelow: "xl", cell: (order) => formatQuantity(order.line_count) },
    { id: "total", header: "Total", align: "right", cell: (order) => <Money value={order.total} /> },
  ];

  const total = list.data?.total ?? 0;
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Orders" subtitle="Read-only. Orders are updated by CSV imports." />
      <section aria-label="Order list" className="rounded-lg border bg-card">
        <div className="flex flex-col gap-3 border-b p-4">
          <div className="flex flex-wrap items-center gap-2">
            <SearchInput label="Search orders" placeholder="Order number or customer reference" value={params.q} onChange={(q) => update({ q })} />
            <MultiSelectFilter
              label="Status"
              options={ORDER_STATUSES.map((s) => ({ value: s, label: orderStatusMeta[s].label, group: STATUS_GROUPS[s] }))}
              selected={params.status}
              onChange={(values) => update({ status: values as OrderParams["status"] })}
            />
            <label className="ml-1 flex h-8 cursor-pointer items-center gap-2 text-body">
              <Checkbox checked={params.overdue} onCheckedChange={(checked) => update({ overdue: checked === true })} />
              Overdue only
            </label>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <SelectField
              label="Payment"
              value={params.payment_status ?? ""}
              options={[{ value: "", label: "Any" }, ...PAYMENT_STATUSES.map((s) => ({ value: s, label: paymentStatusMeta[s].label }))]}
              onChange={(value) => update({ payment_status: (value || null) as OrderParams["payment_status"] })}
            />
            <SelectField
              label="Fulfillment"
              value={params.fulfillment_status ?? ""}
              options={[{ value: "", label: "Any" }, ...FULFILLMENT_STATUSES.map((s) => ({ value: s, label: fulfillmentStatusMeta[s].label }))]}
              onChange={(value) => update({ fulfillment_status: (value || null) as OrderParams["fulfillment_status"] })}
            />
            <SelectField
              label="Channel"
              value={params.channel ?? ""}
              options={[{ value: "", label: "Any" }, ...CHANNELS.map((c) => ({ value: c, label: channelLabels[c] }))]}
              onChange={(value) => update({ channel: (value || null) as OrderParams["channel"] })}
            />
            <SelectField
              label="Placed"
              value={params.placed ?? ""}
              options={[{ value: "", label: "Any time" }, ...Object.entries(PLACED_LABELS).map(([value, label]) => ({ value, label }))]}
              onChange={(value) => update({ placed: (value || null) as OrderParams["placed"] })}
            />
            <SelectField label="Sort" value={params.sort} options={SORT_OPTIONS} onChange={(value) => update({ sort: value as OrderParams["sort"] })} />
            <p className="ml-auto text-sm text-muted-foreground" aria-live="polite">
              {list.data ? formatCount(total, "order") : null}
            </p>
          </div>
          <FilterChips chips={chips} onClearAll={clearAll} />
        </div>
        <DataTable
          caption={`Orders, page ${params.page}, sorted by ${SORT_OPTIONS.find((o) => o.value === params.sort)?.label ?? "placed, newest"}`}
          columns={columns}
          rows={list.data?.items}
          getRowId={(order) => order.id}
          status={list.isPending ? "loading" : list.isError ? "error" : "success"}
          isFetching={list.isPlaceholderData}
          error={list.error}
          onRetry={() => void list.refetch()}
          errorTitle="Couldn't load orders"
          isFiltered={isOrderFiltered(params)}
          renderStackedRow={(order) => (
            <div className="flex flex-col gap-1 p-4">
              <div className="flex items-center gap-2">
                <Link href={hrefFor(order)} className="text-body-strong after:absolute after:inset-0">
                  {order.order_number}
                </Link>
                <OrderStatusPill status={order.status} />
                <span className="ml-auto">
                  <Money value={order.total} />
                </span>
              </div>
              <p className="flex flex-wrap items-center gap-x-2 text-sm text-muted-foreground">
                <span>{formatDateTimeShort(order.placed_at, store.timezone, now)}</span>·
                <AxisText axis="payment" value={order.payment_status} />·
                <AxisText axis="fulfillment" value={order.fulfillment_status} />
              </p>
              {order.ship_by ? (
                <p className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="text-muted-foreground">Ship by {formatDateTimeShort(order.ship_by, store.timezone, now)}</span>
                  <OverdueFlag order={order} now={now} />
                </p>
              ) : null}
            </div>
          )}
          noResults={
            params.overdue && chips.length === 1 ? (
              <EmptyState icon={CircleCheck} variant="success" title="No overdue orders" description="Every paid order is within its ship-by deadline." />
            ) : (
              <EmptyState
                icon={SearchX}
                title="No orders match these filters"
                action={
                  <Button type="button" variant="secondary" onClick={clearAll}>
                    Clear filters
                  </Button>
                }
              />
            )
          }
          empty={
            <EmptyState
              icon={ShoppingCart}
              title="No orders yet"
              description="Orders come from CSV imports (orders.csv, then order_items.csv)."
              action={<ImportLink type="orders" label="Import orders" />}
            />
          }
        />
        {list.data && total > 0 ? (
          <Pagination
            page={params.page}
            pageSize={params.page_size}
            total={total}
            onPageChange={(page) => update({ page }, "push")}
            onPageSizeChange={(size) => update({ page_size: size as OrderParams["page_size"] })}
          />
        ) : null}
      </section>
    </div>
  );
}
