"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import { AlarmClock, ChevronRight, Info, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { DateTime, Money, NoValue } from "@/components/data/values";
import { sectionHref } from "@/components/shell/nav-config";
import { CopyButton } from "@/components/states/copy-button";
import { ErrorState } from "@/components/states/error-state";
import { NotFoundState } from "@/components/states/not-found-state";
import { PermissionDenied } from "@/components/states/permission-denied";
import { AxisText, ExceptionStatusPill, HealthBadge, OrderStatusPill, SeverityBadge } from "@/components/status/status-pill";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { isApiError } from "@/lib/api/errors";
import { ordersApi, orderKeys, type LinkedException, type OrderDetail } from "@/lib/api/orders-api";
import { formatDue } from "@/lib/format/datetime";
import { formatQuantity } from "@/lib/format/number";
import { useDocumentTitle } from "@/lib/hooks/use-document-title";
import { useNow } from "@/lib/hooks/use-now";
import { changeSourceLabels, channelLabels, exceptionTypeLabels, orderStatusMeta, reservationLabels, type OrderStatus } from "@/lib/status-maps";
import { useStore } from "@/lib/store/store-context";

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section aria-labelledby={`${id}-title`} className="rounded-lg border bg-card p-4 md:p-5">
      <h2 id={`${id}-title`} className="mb-3 text-title-sm">
        {title}
      </h2>
      {children}
    </section>
  );
}

function DescriptionList({ items, columns = 2 }: { items: Array<[string, React.ReactNode]>; columns?: 1 | 2 }) {
  return (
    <dl className={columns === 2 ? "grid gap-x-8 gap-y-2 md:grid-cols-2" : "grid gap-y-2"}>
      {items.map(([term, value]) => (
        <div key={term} className="flex justify-between gap-4 border-b pb-2 text-body last:border-b-0 md:block md:border-b-0 md:pb-0">
          <dt className="text-muted-foreground">{term}</dt>
          <dd className="text-right md:text-left">{value ?? <NoValue />}</dd>
        </div>
      ))}
    </dl>
  );
}

/** Three separate facts: lifecycle, money and goods (STATE_MACHINES §1). */
function StatusCard({ order, refundException }: { order: OrderDetail; refundException?: LinkedException }) {
  const store = useStore();
  return (
    <Section id="status" title="Status">
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">Status</span>
          <OrderStatusPill status={order.status} size="md" />
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">Payment</span>
          <AxisText axis="payment" value={order.payment_status} />
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">Fulfillment</span>
          <AxisText axis="fulfillment" value={order.fulfillment_status} />
        </div>
      </div>
      <p className="mt-3 flex items-center gap-1 text-xs font-normal text-muted-foreground">
        <Info aria-hidden className="size-3.5" />
        Orders track three separate facts: lifecycle, money and goods.
      </p>
      {order.status === "CANCELLED" && order.payment_status === "PAID" ? (
        <Alert tone="warning" className="mt-3">
          <TriangleAlert aria-hidden />
          <AlertDescription>
            <p>
              Cancelled but still paid: a refund is pending.
              {refundException ? (
                <>
                  {" "}
                  See{" "}
                  <Link href={`/s/${store.id}/exceptions/${refundException.id}`} className="text-link hover:underline">
                    {refundException.reference}
                  </Link>
                  .
                </>
              ) : null}
            </p>
          </AlertDescription>
        </Alert>
      ) : null}
      {order.status === "REFUNDED" && order.fulfillment_status === "DELIVERED" ? (
        <Alert tone="info" className="mt-3">
          <Info aria-hidden />
          <AlertDescription>
            <p>Refunded without a return: the customer kept the goods.</p>
          </AlertDescription>
        </Alert>
      ) : null}
    </Section>
  );
}

/** An exception's reference, linked to its page when the person can open exceptions. */
function ExceptionLink({ exception, stretched = false }: { exception: LinkedException; stretched?: boolean }) {
  const store = useStore();
  if (!sectionHref(store.id, "exceptions", store.permissions)) return <>{exception.reference}</>;
  return (
    <Link
      href={`/s/${store.id}/exceptions/${exception.id}`}
      className={stretched ? "text-link after:absolute after:inset-0 hover:underline" : "text-link hover:underline"}
    >
      {exception.reference}
    </Link>
  );
}

/** "Paid → Shipped, via Processing, Ready to ship". */
export function transitionText(from: OrderStatus | null, to: OrderStatus, skipped: string[]): string {
  const label = (status: string) => orderStatusMeta[status as OrderStatus]?.label ?? status;
  const head = from ? `${label(from)} → ${label(to)}` : to === "CREATED" ? "Created" : `Created: ${label(to)}`;
  return skipped.length ? `${head}, via ${skipped.map(label).join(", ")}` : head;
}

/** One order across its status axes, lines, history and exceptions (SCREEN_SPECIFICATIONS S-06). */
export function OrderScreen() {
  const store = useStore();
  const now = useNow();
  const { orderId } = useParams<{ orderId: string }>();
  const canRead = store.permissions.has("orders.read");
  const order = useQuery({
    queryKey: orderKeys.detail(store.id, orderId),
    queryFn: ({ signal }) => ordersApi.detail(store.id, orderId, signal),
    enabled: canRead,
  });
  const storeDetail = useQuery({
    queryKey: orderKeys.store(store.id),
    queryFn: ({ signal }) => ordersApi.store(store.id, signal),
    enabled: canRead && store.permissions.has("dashboard.read"),
    staleTime: 5 * 60_000,
  });
  const skus = [...new Set(order.data?.lines.map((line) => line.sku) ?? [])];
  const canSeeStock = store.permissions.has("inventory.read");
  const positions = useQueries({
    queries: skus.map((sku) => ({
      queryKey: orderKeys.position(store.id, sku),
      queryFn: ({ signal }: { signal: AbortSignal }) => ordersApi.positions(store.id, { q: sku, include_inactive: true, page_size: 5 }, signal),
      enabled: canSeeStock,
      select: (page: Awaited<ReturnType<typeof ordersApi.positions>>) => page.items.find((item) => item.sku === sku),
    })),
  });
  useDocumentTitle(order.data ? `Order ${order.data.order_number}` : "Order");

  if (!canRead) return <PermissionDenied pageName="orders" permission="orders.read" />;

  const listHref = `/s/${store.id}/orders`;
  const breadcrumb = (
    <nav aria-label="Breadcrumb" className="text-sm">
      <ol className="flex items-center gap-1 text-muted-foreground">
        <li>
          <Link href={listHref} className="hover:text-foreground hover:underline">
            Orders
          </Link>
        </li>
        <li aria-hidden>
          <ChevronRight className="size-3.5" />
        </li>
        <li aria-current="page" className="text-foreground">
          {order.data?.order_number ?? "Order"}
        </li>
      </ol>
    </nav>
  );

  if (order.isPending) {
    return (
      <div aria-busy="true" className="flex flex-col gap-4">
        {breadcrumb}
        <span className="sr-only" role="status">
          Loading order
        </span>
        <Skeleton className="h-7 w-64" />
        <Skeleton className="h-28 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }
  if (order.isError) {
    if (isApiError(order.error) && order.error.status === 404) {
      return <NotFoundState entity="order" backHref={listHref} backLabel="Back to orders" />;
    }
    return (
      <div className="flex flex-col gap-4">
        {breadcrumb}
        <ErrorState size="page" title="Couldn't load this order" error={order.error} onRetry={() => void order.refetch()} />
      </div>
    );
  }

  const data = order.data;
  const amounts = data.amounts;
  const slaHours = storeDetail.data?.settings.fulfillment_sla_hours;
  const exceptions = data.exceptions;
  const active = exceptions.filter((item) => item.is_active);
  const closed = exceptions.filter((item) => !item.is_active).slice(0, 5);
  const mismatch = exceptions.find((item) => item.exception_type === "DATA_ORDER_TOTAL_MISMATCH" && item.is_active) ??
    exceptions.find((item) => item.exception_type === "DATA_ORDER_TOTAL_MISMATCH");
  const refund = exceptions.find((item) => item.exception_type === "ORDER_REFUND_PENDING" && item.is_active);
  const productHref = sectionHref(store.id, "products", store.permissions);
  const events = [...data.events].sort((a, b) => b.occurred_at.localeCompare(a.occurred_at));

  return (
    <div className="flex flex-col gap-6">
      {breadcrumb}
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <h1 tabIndex={-1} className="text-title-lg outline-none">
            Order {data.order_number}
          </h1>
          <OrderStatusPill status={data.status} size="md" />
          {data.is_overdue && data.ship_by ? (
            <span className="inline-flex items-center gap-1 text-body text-overdue">
              <AlarmClock aria-hidden className="size-4" />
              {formatDue(data.ship_by, now).text}
            </span>
          ) : null}
        </div>
        <p className="text-sm text-muted-foreground">
          Placed <DateTime value={data.placed_at} /> · {channelLabels[data.channel]}
          {data.customer_ref ? ` · Customer ${data.customer_ref}` : ""} · {amounts.currency}
        </p>
      </div>

      <div className="grid grid-cols-1 items-start gap-6 xl:grid-cols-[minmax(0,1fr)_var(--aside-w)]">
        <div className="flex min-w-0 flex-col gap-6">
          <StatusCard order={data} refundException={refund} />

          <Section id="dates" title="Key dates">
            <DescriptionList
              items={[
                ["Placed", <DateTime key="placed" value={data.placed_at} />],
                ["Paid", data.paid_at ? <DateTime value={data.paid_at} /> : null],
                [
                  "Ship by",
                  data.ship_by ? (
                    <span>
                      <DateTime value={data.ship_by} />{" "}
                      <span className="text-xs text-muted-foreground">
                        {data.ship_by_source === "IMPORTED"
                          ? "(Imported)"
                          : data.ship_by_source === "STORE_SLA"
                            ? `(Store SLA${slaHours ? `: paid + ${slaHours} h` : ""})`
                            : ""}
                      </span>
                    </span>
                  ) : null,
                ],
                ["Shipped", data.shipped_at ? <DateTime value={data.shipped_at} /> : null],
                ["Delivered", data.delivered_at ? <DateTime value={data.delivered_at} /> : null],
                ["Cancelled", data.cancelled_at ? <DateTime value={data.cancelled_at} /> : null],
                ["Carrier", data.carrier],
                [
                  "Tracking number",
                  data.tracking_number ? (
                    <span className="inline-flex items-center gap-1">
                      <code className="font-mono text-mono">{data.tracking_number}</code>
                      <CopyButton value={data.tracking_number} label="Copy tracking number" />
                    </span>
                  ) : null,
                ],
              ]}
            />
          </Section>

          <Section id="lines" title={`Line items (${data.lines.length})`}>
            {data.lines.length === 0 ? (
              <p className="text-body text-muted-foreground">This order has no lines yet. Import order_items.csv.</p>
            ) : (
              <div className="relative overflow-x-auto rounded-md border">
                <table className="w-full text-sm">
                  <caption className="sr-only">Line items</caption>
                  <thead className="bg-surface-subtle text-xs text-muted-foreground">
                    <tr>
                      <th scope="col" className="sticky left-0 h-8 bg-surface-subtle px-3 text-left font-medium">SKU</th>
                      <th scope="col" className="px-3 text-left font-medium">Product</th>
                      <th scope="col" className="px-3 text-right font-medium">Qty</th>
                      <th scope="col" className="px-3 text-right font-medium">Unit price</th>
                      <th scope="col" className="px-3 text-right font-medium">Discount</th>
                      <th scope="col" className="px-3 text-right font-medium">Line total</th>
                      <th scope="col" className="px-3 text-left font-medium">Reservation</th>
                      {canSeeStock ? <th scope="col" className="px-3 text-left font-medium">Stock</th> : null}
                    </tr>
                  </thead>
                  <tbody>
                    {data.lines.map((line, index) => {
                      const position = positions[skus.indexOf(line.sku)]?.data;
                      return (
                        <tr key={line.id} className="border-t">
                          <td className="sticky left-0 h-9 bg-card px-3 font-medium whitespace-nowrap">
                            {productHref ? (
                              <Link href={`/s/${store.id}/products/${line.product_id}`} className="text-link hover:underline">
                                {line.sku}
                              </Link>
                            ) : (
                              line.sku
                            )}
                          </td>
                          <td className="px-3">{line.product_name}</td>
                          <td className="px-3 text-right tabular-nums">{formatQuantity(line.quantity)}</td>
                          <td className="px-3 text-right"><Money value={line.unit_price} /></td>
                          <td className="px-3 text-right">{Number(line.line_discount) === 0 ? <NoValue /> : <Money value={line.line_discount} />}</td>
                          <td className="px-3 text-right"><Money value={line.line_total} /></td>
                          <td className="px-3 whitespace-nowrap text-muted-foreground">
                            {line.reservation ? `${reservationLabels[line.reservation.status]} · ${formatQuantity(line.reservation.quantity)}` : "—"}
                          </td>
                          {canSeeStock ? (
                            <td className="px-3" data-line={index}>
                              {position ? <HealthBadge health={position.health} onHand={position.on_hand} /> : <NoValue />}
                            </td>
                          ) : null}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Section>

          <Section id="history" title="Status history">
            <ol className="flex flex-col">
              {events.map((event) => (
                <li key={event.id} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-t py-2 text-body first:border-t-0">
                  <span className="min-w-0 flex-1">{transitionText(event.from_status, event.to_status, event.skipped_statuses)}</span>
                  <span className="rounded-sm bg-tone-neutral-bg px-1.5 text-xs text-tone-neutral-fg">{changeSourceLabels[event.source]}</span>
                  <span className="text-sm text-muted-foreground">
                    <DateTime value={event.occurred_at} />
                  </span>
                </li>
              ))}
            </ol>
          </Section>
        </div>

        <aside aria-label="Order totals and exceptions" className="flex flex-col gap-6">
          <Section id="totals" title="Totals">
            <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1.5 text-body">
              {(
                [
                  ["Subtotal", amounts.subtotal],
                  ["Discounts", amounts.discount_total],
                  ["Shipping", amounts.shipping_total],
                  ["Tax", amounts.tax_total],
                ] as const
              ).map(([term, value]) => (
                <div key={term} className="contents">
                  <dt className="text-muted-foreground">{term}</dt>
                  <dd className="text-right"><Money value={value} /></dd>
                </div>
              ))}
              <dt className="border-t pt-1.5 font-medium">Total (recorded)</dt>
              <dd className="border-t pt-1.5 text-right font-medium"><Money value={amounts.total} /></dd>
              <dt className="text-muted-foreground">Lines total</dt>
              <dd className="text-right"><Money value={amounts.lines_total} /></dd>
              {amounts.has_total_mismatch ? (
                <>
                  <dt className="text-tone-danger-fg">Expected total</dt>
                  <dd className="text-right text-tone-danger-fg"><Money value={amounts.expected_total} /></dd>
                  <dt className="text-tone-danger-fg">Difference</dt>
                  <dd className="text-right text-tone-danger-fg"><Money value={amounts.difference} /></dd>
                </>
              ) : null}
            </dl>
            {amounts.has_total_mismatch && mismatch ? (
              <p className="mt-2 text-sm">
                The recorded total doesn&apos;t match its parts. See{" "}
                <ExceptionLink exception={mismatch} />.
              </p>
            ) : null}
          </Section>

          {store.permissions.has("exceptions.read") ? (
            <Section id="exceptions" title="Exceptions">
              {exceptions.length === 0 ? (
                <p className="text-body text-muted-foreground">No exceptions involve this order.</p>
              ) : (
                <ul className="flex flex-col">
                  {[...active, ...closed].map((item) => (
                    <li key={item.id} className="relative flex flex-col gap-1 border-t py-2 first:border-t-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-body-strong"><ExceptionLink exception={item} stretched /></span>
                        <SeverityBadge severity={item.severity} />
                        <ExceptionStatusPill status={item.status} resolutionCode={item.resolution_code} verifiedAt={item.verified_at} />
                      </div>
                      <p className="text-sm">{item.title}</p>
                      <p className="text-xs font-normal text-muted-foreground">
                        {exceptionTypeLabels[item.exception_type]} · {item.link_role === "PRIMARY" ? "About this order" : "Affects this order"}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </Section>
          ) : null}
        </aside>
      </div>
    </div>
  );
}
