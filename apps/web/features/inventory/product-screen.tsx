"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronRight, Database } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { EstimateValue } from "@/components/data/estimate";
import { DateTime, Money, NoValue } from "@/components/data/values";
import { sectionHref } from "@/components/shell/nav-config";
import { ErrorState } from "@/components/states/error-state";
import { NotFoundState } from "@/components/states/not-found-state";
import { PermissionDenied } from "@/components/states/permission-denied";
import { ExceptionStatusPill, HealthBadge, ProductStatusTag, SeverityBadge } from "@/components/status/status-pill";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { isApiError } from "@/lib/api/errors";
import type { ExceptionListItem } from "@/lib/api/exceptions-api";
import { inventoryApi, inventoryKeys, type ProductDetail } from "@/lib/api/inventory-api";
import { storeApi, storeKeys } from "@/lib/api/store-api";
import { formatDate } from "@/lib/format/datetime";
import { formatDelta, formatQuantity } from "@/lib/format/number";
import { useDocumentTitle } from "@/lib/hooks/use-document-title";
import { displayHealth, exceptionTypeLabels, movementTypeLabels } from "@/lib/status-maps";
import { useStore } from "@/lib/store/store-context";
import { cn } from "@/lib/utils";

const MINUS = "−";
const signed = (value: number) => (value < 0 ? `${MINUS}${Math.abs(value)}` : String(value));

function Section({ id, title, children, aside }: { id: string; title: string; children: React.ReactNode; aside?: React.ReactNode }) {
  return (
    <section aria-labelledby={`${id}-title`} className="rounded-lg border bg-card p-4 md:p-5">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 id={`${id}-title`} className="text-title-sm">
          {title}
        </h2>
        {aside}
      </div>
      {children}
    </section>
  );
}

function StatTile({ label, children, hint }: { label: string; children: React.ReactNode; hint?: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1 rounded-md border p-3">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-title tabular-nums">{children}</span>
      {hint ? <span className="text-xs font-normal text-muted-foreground">{hint}</span> : null}
    </div>
  );
}

/** Why the product has its stock health (S-08), in the rule's own terms. */
export function healthExplanation(product: ProductDetail): string | null {
  const { reorder_point: reorder, approaching_threshold: threshold } = product;
  switch (product.health) {
    case "OVERSOLD":
      return "Oversold: available is below 0.";
    case "OUT_OF_STOCK":
      return "Out of stock: available is 0.";
    case "BELOW_REORDER_POINT":
      return `Below reorder point: available is at or below the reorder point (${reorder}).`;
    // The approaching threshold comes from the API, which applies the store's factor (BR-140).
    case "APPROACHING_REORDER_POINT":
      return threshold
        ? `Reorder point ${reorder}. Approaching covers available ${reorder + 1} to ${threshold}.`
        : `Approaching the reorder point (${reorder}).`;
    case "HEALTHY":
      if (reorder === 0) return "Healthy: stock is available and no reorder point is set.";
      return threshold ? `Healthy: available is above ${threshold}, the approaching threshold for reorder point ${reorder}.` : "Healthy.";
    default:
      return product.status === "ACTIVE" ? null : "Stock health is computed for active products only.";
  }
}

function StockPosition({ product, dataIssueException }: { product: ProductDetail; dataIssueException?: ExceptionListItem }) {
  const store = useStore();
  const { stock } = product;
  const dataIssue = displayHealth(product.health, stock.on_hand) === "DATA_ISSUE";
  return (
    <Section id="stock" title="Stock position">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <StatTile label="On hand">
          <span className={cn(stock.on_hand < 0 && "text-tone-danger-fg")}>{formatQuantity(stock.on_hand)}</span>
        </StatTile>
        <StatTile label="Reserved">{formatQuantity(stock.reserved)}</StatTile>
        <StatTile label="Available" hint={dataIssue ? "not reliable" : undefined}>
          <span className={cn(stock.available < 0 && "text-tone-danger-fg")}>{formatQuantity(stock.available)}</span>
        </StatTile>
        <StatTile label="Incoming" hint={stock.incoming_eta ? `ETA ${formatDate(stock.incoming_eta, store.timezone)}` : undefined}>
          {formatQuantity(stock.incoming)}
        </StatTile>
        <StatTile label="Avg daily units">
          <EstimateValue estimate={product.avg_daily_units} />
        </StatTile>
        <StatTile label="Days of cover" hint={dataIssue ? "not reliable" : undefined}>
          {dataIssue ? <NoValue /> : <EstimateValue estimate={product.days_of_cover} unit="days" />}
        </StatTile>
      </div>
      <p className="mt-3 font-mono text-mono break-words">
        available = on_hand {MINUS} reserved = {signed(stock.on_hand)} {MINUS} {stock.reserved} = {signed(stock.available)} (BR-101).
        Incoming is not counted (BR-103).
      </p>
      {dataIssue ? (
        <Alert tone="attention" className="mt-3">
          <Database aria-hidden />
          <AlertDescription>
            <p>
              Data issue: on hand is {signed(stock.on_hand)}, which is physically impossible. Stock health and inventory exceptions are
              suspended for this product until a cycle count corrects it (BR-402a).
              {dataIssueException ? (
                <>
                  {" "}
                  See{" "}
                  <Link href={`/s/${store.id}/exceptions/${dataIssueException.id}`} className="text-link hover:underline">
                    {dataIssueException.reference}
                  </Link>{" "}
                  ({exceptionTypeLabels[dataIssueException.exception_type]}).
                </>
              ) : null}
            </p>
          </AlertDescription>
        </Alert>
      ) : healthExplanation(product) ? (
        <p className="mt-2 text-sm text-muted-foreground">{healthExplanation(product)}</p>
      ) : null}
    </Section>
  );
}

/** The hub for one SKU: master data, stock arithmetic, exceptions and ledger (SCREEN_SPECIFICATIONS S-08). */
export function ProductScreen() {
  const store = useStore();
  const { productId } = useParams<{ productId: string }>();
  const canRead = store.permissions.has("catalog.read");
  const canSeeStock = store.permissions.has("inventory.read");
  const canSeeExceptions = store.permissions.has("exceptions.read");

  const product = useQuery({
    queryKey: inventoryKeys.product(store.id, productId),
    queryFn: ({ signal }) => inventoryApi.product(store.id, productId, signal),
    enabled: canRead,
  });
  const activeQuery = { product_id: productId, page_size: 25 };
  const closedQuery = { product_id: productId, status: ["RESOLVED", "DISMISSED"], sort: "-last_detected_at", page_size: 5 };
  const active = useQuery({
    queryKey: storeKeys.exceptions(store.id, activeQuery),
    queryFn: ({ signal }) => storeApi.exceptions(store.id, activeQuery, signal),
    enabled: canRead && canSeeExceptions,
  });
  const closed = useQuery({
    queryKey: storeKeys.exceptions(store.id, closedQuery),
    queryFn: ({ signal }) => storeApi.exceptions(store.id, closedQuery, signal),
    enabled: canRead && canSeeExceptions,
  });
  const movementsQuery = { product_id: productId, sort: "-occurred_at", page_size: 10 };
  const movements = useQuery({
    queryKey: inventoryKeys.movements(store.id, movementsQuery),
    queryFn: ({ signal }) => inventoryApi.movements(store.id, movementsQuery, signal),
    enabled: canRead && canSeeStock,
  });
  useDocumentTitle(product.data?.sku ?? "Product");

  if (!canRead) return <PermissionDenied pageName="products" permission="catalog.read" />;

  const listHref = `/s/${store.id}/products`;
  const breadcrumb = (
    <nav aria-label="Breadcrumb" className="text-sm">
      <ol className="flex items-center gap-1 text-muted-foreground">
        <li>
          <Link href={listHref} className="hover:text-foreground hover:underline">
            Products
          </Link>
        </li>
        <li aria-hidden>
          <ChevronRight className="size-3.5" />
        </li>
        <li aria-current="page" className="text-foreground">
          {product.data?.sku ?? "Product"}
        </li>
      </ol>
    </nav>
  );

  if (product.isPending) {
    return (
      <div aria-busy="true" className="flex flex-col gap-4">
        {breadcrumb}
        <span className="sr-only" role="status">
          Loading product
        </span>
        <Skeleton className="h-7 w-72" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }
  if (product.isError) {
    if (isApiError(product.error) && product.error.status === 404) {
      return <NotFoundState entity="product" backHref={listHref} backLabel="Back to products" />;
    }
    return (
      <div className="flex flex-col gap-4">
        {breadcrumb}
        <ErrorState size="page" title="Couldn't load this product" error={product.error} onRetry={() => void product.refetch()} />
      </div>
    );
  }

  const data = product.data;
  const exceptions = [...(active.data?.items ?? []), ...(closed.data?.items ?? [])];
  const dataIssueException = active.data?.items.find((item) => item.exception_type === "DATA_NEGATIVE_ON_HAND");
  const movementsHref = sectionHref(store.id, "inventory/movements", store.permissions, { product_id: data.id });

  return (
    <div className="flex flex-col gap-6">
      {breadcrumb}
      <div className="flex flex-col gap-2">
        <h1 tabIndex={-1} className="text-title-lg outline-none">
          {data.name}
        </h1>
        <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          <span className="font-medium text-foreground">{data.sku}</span>
          {data.category ? <span>· {data.category}</span> : null}
          <ProductStatusTag status={data.status} />
          {canSeeStock ? <HealthBadge health={data.health} onHand={data.stock.on_hand} size="md" /> : null}
        </div>
      </div>

      {canSeeStock ? <StockPosition product={data} dataIssueException={dataIssueException} /> : null}

      <div className="grid grid-cols-1 items-start gap-6 xl:grid-cols-2">
        <Section id="product" title="Product">
          <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-1.5 text-body">
            <dt className="text-muted-foreground">Price</dt>
            <dd><Money value={data.unit_price} /></dd>
            <dt className="text-muted-foreground">Cost</dt>
            <dd>{data.unit_cost === null ? <NoValue /> : <Money value={data.unit_cost} />}</dd>
            <dt className="text-muted-foreground">Reorder point</dt>
            <dd className="tabular-nums">{formatQuantity(data.reorder_point)}</dd>
            <dt className="text-muted-foreground">Reorder quantity</dt>
            <dd className="tabular-nums">{data.reorder_quantity === null ? <NoValue /> : formatQuantity(data.reorder_quantity)}</dd>
            <dt className="text-muted-foreground">Supplier</dt>
            <dd>
              {data.supplier ? `${data.supplier.name}${data.supplier.lead_time_days ? ` (lead time ${data.supplier.lead_time_days} days)` : ""}` : <NoValue />}
            </dd>
            <dt className="text-muted-foreground">Last cycle count</dt>
            <dd>{data.stock.last_cycle_count_at ? <DateTime value={data.stock.last_cycle_count_at} /> : <NoValue />}</dd>
          </dl>
        </Section>

        {canSeeExceptions ? (
          <Section id="exceptions" title={`Exceptions (${data.active_exception_count} active)`}>
            {active.isPending || closed.isPending ? (
              <Skeleton className="h-20 w-full" />
            ) : exceptions.length === 0 ? (
              <p className="text-body text-muted-foreground">No exceptions involve this product.</p>
            ) : (
              <ul className="flex flex-col">
                {exceptions.map((item) => (
                  <li key={item.id} className="relative flex flex-col gap-1 border-t py-2 first:border-t-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <Link href={`/s/${store.id}/exceptions/${item.id}`} className="text-body-strong text-link after:absolute after:inset-0 hover:underline">
                        {item.reference}
                      </Link>
                      <SeverityBadge severity={item.severity} />
                      <ExceptionStatusPill status={item.status} resolutionCode={item.resolution_code} verifiedAt={item.verified_at} />
                    </div>
                    <p className="text-sm">{item.title}</p>
                  </li>
                ))}
              </ul>
            )}
          </Section>
        ) : null}
      </div>

      {canSeeStock ? (
        <Section
          id="movements"
          title="Recent movements"
          aside={
            movementsHref ? (
              <Link href={movementsHref} className="text-sm text-link hover:underline">
                View all movements
              </Link>
            ) : undefined
          }
        >
          {movements.isPending ? (
            <Skeleton className="h-24 w-full" />
          ) : movements.isError ? (
            <ErrorState title="Couldn't load movements" error={movements.error} onRetry={() => void movements.refetch()} />
          ) : movements.data.items.length === 0 ? (
            <p className="text-body text-muted-foreground">No ledger entries yet. Stock arrives through inventory adjustment imports.</p>
          ) : (
            <div className="relative overflow-x-auto rounded-md border">
              <table className="w-full text-sm">
                <caption className="sr-only">Recent movements</caption>
                <thead className="bg-surface-subtle text-xs text-muted-foreground">
                  <tr>
                    <th scope="col" className="h-8 px-3 text-left font-medium">Occurred</th>
                    <th scope="col" className="px-3 text-left font-medium">Type</th>
                    <th scope="col" className="px-3 text-right font-medium">On hand Δ</th>
                    <th scope="col" className="px-3 text-right font-medium">On hand after</th>
                    <th scope="col" className="px-3 text-left font-medium">Note</th>
                  </tr>
                </thead>
                <tbody>
                  {movements.data.items.map((movement) => (
                    <tr key={movement.id} className="border-t">
                      <td className="h-9 px-3 whitespace-nowrap"><DateTime value={movement.occurred_at} compact /></td>
                      <td className="px-3 whitespace-nowrap">{movementTypeLabels[movement.movement_type]}</td>
                      <td className={cn("px-3 text-right tabular-nums", movement.on_hand_delta < 0 && "text-tone-danger-fg")}>{formatDelta(movement.on_hand_delta)}</td>
                      <td className="px-3 text-right tabular-nums">{formatQuantity(movement.on_hand_after)}</td>
                      <td className="max-w-60 truncate px-3 text-muted-foreground" title={movement.note ?? undefined}>{movement.note ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Section>
      ) : null}
    </div>
  );
}
