"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { CircleAlert, SearchX, Tag } from "lucide-react";
import Link from "next/link";

import { DataTable, type Column } from "@/components/data/data-table";
import { FilterChips, MultiSelectFilter, Pagination, SearchInput, SelectField, type Chip } from "@/components/data/list-controls";
import { Money, NoValue } from "@/components/data/values";
import { PageHeader } from "@/components/shell/page-header";
import { EmptyState } from "@/components/states/empty-state";
import { PermissionDenied } from "@/components/states/permission-denied";
import { HealthBadge, ProductStatusTag } from "@/components/status/status-pill";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { inventoryApi, inventoryKeys, type ProductListItem } from "@/lib/api/inventory-api";
import { formatCount, formatQuantity } from "@/lib/format/number";
import { useDocumentTitle } from "@/lib/hooks/use-document-title";
import { useListState } from "@/lib/hooks/use-list-state";
import { defineListParams } from "@/lib/list-params";
import { productStatusMeta, stockHealthMeta, type ProductStatus, type StockHealth } from "@/lib/status-maps";
import { useStore } from "@/lib/store/store-context";
import { cn } from "@/lib/utils";

const HEALTH: StockHealth[] = ["OVERSOLD", "OUT_OF_STOCK", "BELOW_REORDER_POINT", "APPROACHING_REORDER_POINT", "HEALTHY"];

export const productsList = defineListParams(
  {
    q: { kind: "text", max: 100 },
    status: { kind: "one", values: ["ACTIVE", "DRAFT", "ARCHIVED", "ALL"], fallback: "ACTIVE" },
    category: { kind: "text", max: 100 },
    supplier_id: { kind: "id" },
    health: { kind: "many", values: HEALTH },
  },
  { sorts: ["sku", "name", "-updated_at", "available"], defaultSort: "sku", pageSizes: [25, 50, 100], defaultPageSize: 25 },
);

const SORT_OPTIONS = [
  { value: "sku", label: "SKU" },
  { value: "name", label: "Name" },
  { value: "-updated_at", label: "Recently updated" },
  { value: "available", label: "Available, lowest" },
];

/** Catalog list (SCREEN_SPECIFICATIONS S-07). Read-only: products change through CSV imports. */
export function ProductsScreen() {
  const store = useStore();
  useDocumentTitle("Products");
  const canRead = store.permissions.has("catalog.read");
  const canSeeStock = store.permissions.has("inventory.read");
  const { params, update, clearAll, isFiltered } = useListState(productsList);

  const query = {
    q: params.q.trim() || undefined,
    status: params.status === "ALL" ? undefined : params.status,
    category: params.category || undefined,
    supplier_id: params.supplier_id ?? undefined,
    health: params.health,
    sort: params.sort,
    page: params.page,
    page_size: params.page_size,
  };
  const list = useQuery({
    queryKey: inventoryKeys.products(store.id, query),
    queryFn: ({ signal }) => inventoryApi.products(store.id, query, signal),
    placeholderData: keepPreviousData,
    enabled: canRead,
  });
  const categories = useQuery({
    queryKey: inventoryKeys.categories(store.id),
    queryFn: ({ signal }) => inventoryApi.categories(store.id, signal),
    enabled: canRead,
    staleTime: 5 * 60_000,
  });
  const suppliers = useQuery({
    queryKey: inventoryKeys.suppliers(store.id),
    queryFn: ({ signal }) => inventoryApi.suppliers(store.id, signal),
    enabled: canRead,
    staleTime: 5 * 60_000,
  });

  if (!canRead) return <PermissionDenied pageName="products" permission="catalog.read" />;

  const hrefFor = (product: ProductListItem) => `/s/${store.id}/products/${product.id}`;
  const supplierName = (id: string) => suppliers.data?.items.find((supplier) => supplier.id === id)?.name ?? "Selected supplier";
  const chips: Chip[] = [
    ...(params.q ? [{ key: "q", label: `Search: ${params.q}`, onRemove: () => update({ q: "" }) }] : []),
    ...(params.status !== "ACTIVE"
      ? [{ key: "status", label: `Status: ${params.status === "ALL" ? "Any" : productStatusMeta[params.status as ProductStatus].label}`, onRemove: () => update({ status: "ACTIVE" }) }]
      : []),
    ...(params.category ? [{ key: "category", label: `Category: ${params.category}`, onRemove: () => update({ category: "" }) }] : []),
    ...(params.supplier_id ? [{ key: "supplier", label: `Supplier: ${supplierName(params.supplier_id)}`, onRemove: () => update({ supplier_id: null }) }] : []),
    ...(params.health.length
      ? [{ key: "health", label: `Stock: ${params.health.map((h) => stockHealthMeta[h as StockHealth].label).join(", ")}`, onRemove: () => update({ health: [] }) }]
      : []),
  ];

  const columns: Column<ProductListItem>[] = [
    {
      id: "sku",
      header: "SKU",
      cell: (product) => (
        <Link href={hrefFor(product)} className="font-medium whitespace-nowrap outline-offset-[-2px] after:absolute after:inset-0 hover:underline">
          {product.sku}
        </Link>
      ),
    },
    { id: "name", header: "Name", cell: (product) => <span className="line-clamp-2">{product.name}</span> },
    { id: "category", header: "Category", hideBelow: "lg", cell: (product) => product.category ?? <NoValue /> },
    { id: "status", header: "Status", hideBelow: "md", cell: (product) => <ProductStatusTag status={product.status} /> },
    { id: "price", header: "Price", align: "right", cell: (product) => <Money value={product.unit_price} /> },
    {
      id: "cost",
      header: "Cost",
      align: "right",
      hideBelow: "lg",
      cell: (product) =>
        product.unit_cost === null ? (
          <NoValue />
        ) : (
          <span className="inline-flex items-center justify-end gap-1">
            {Number(product.unit_cost) > Number(product.unit_price) ? (
              <Tooltip>
                <TooltipTrigger asChild>
                  <button type="button" aria-label="Unit cost is higher than unit price." className="relative z-[1] text-tone-warning-fg">
                    <CircleAlert aria-hidden className="size-3.5" />
                  </button>
                </TooltipTrigger>
                <TooltipContent>Unit cost is higher than unit price.</TooltipContent>
              </Tooltip>
            ) : null}
            <Money value={product.unit_cost} />
          </span>
        ),
    },
    { id: "supplier", header: "Supplier", hideBelow: "xl", cell: (product) => product.supplier?.name ?? <NoValue /> },
    {
      id: "reorder",
      header: "Reorder point / qty",
      align: "right",
      hideBelow: "lg",
      cell: (product) => `${formatQuantity(product.reorder_point)} / ${product.reorder_quantity === null ? "—" : formatQuantity(product.reorder_quantity)}`,
    },
    ...(canSeeStock
      ? ([
          {
            id: "available",
            header: "Available",
            align: "right",
            hideBelow: "md",
            cell: (product) => <span className={cn(product.available < 0 && "text-tone-danger-fg")}>{formatQuantity(product.available)}</span>,
          },
          {
            id: "stock",
            header: "Stock",
            cell: (product) => <HealthBadge health={product.health} onHand={product.on_hand} />,
          },
        ] satisfies Column<ProductListItem>[])
      : []),
  ];

  const total = list.data?.total ?? 0;
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Products" subtitle="Read-only. The catalog is updated by CSV imports." />
      <section aria-label="Product list" className="rounded-lg border bg-card">
        <div className="flex flex-col gap-3 border-b p-4">
          <div className="flex flex-wrap items-center gap-2">
            <SearchInput label="Search products" placeholder="SKU or name" value={params.q} onChange={(q) => update({ q })} />
            {canSeeStock ? (
              <MultiSelectFilter
                label="Stock"
                options={HEALTH.map((h) => ({ value: h, label: stockHealthMeta[h].label }))}
                selected={params.health}
                onChange={(health) => update({ health })}
              />
            ) : null}
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <SelectField
              label="Status"
              value={params.status ?? "ACTIVE"}
              options={[
                { value: "ACTIVE", label: "Active" },
                { value: "DRAFT", label: "Draft" },
                { value: "ARCHIVED", label: "Archived" },
                { value: "ALL", label: "Any" },
              ]}
              onChange={(status) => update({ status })}
            />
            <SelectField
              label="Category"
              value={params.category}
              options={[{ value: "", label: "Any" }, ...(categories.data?.items ?? []).map((category) => ({ value: category, label: category }))]}
              onChange={(category) => update({ category })}
            />
            <SelectField
              label="Supplier"
              value={params.supplier_id ?? ""}
              options={[{ value: "", label: "Any" }, ...(suppliers.data?.items ?? []).map((supplier) => ({ value: supplier.id, label: supplier.name }))]}
              onChange={(value) => update({ supplier_id: value || null })}
            />
            <SelectField label="Sort" value={params.sort} options={SORT_OPTIONS} onChange={(sort) => update({ sort })} />
            <p className="ml-auto text-sm text-muted-foreground" aria-live="polite">
              {list.data ? formatCount(total, "product") : null}
            </p>
          </div>
          <FilterChips chips={chips} onClearAll={clearAll} />
        </div>
        <DataTable
          caption={`Products, page ${params.page}, sorted by ${SORT_OPTIONS.find((o) => o.value === params.sort)?.label ?? "SKU"}`}
          columns={columns}
          rows={list.data?.items}
          getRowId={(product) => product.id}
          status={list.isPending ? "loading" : list.isError ? "error" : "success"}
          isFetching={list.isPlaceholderData}
          error={list.error}
          onRetry={() => void list.refetch()}
          errorTitle="Couldn't load products"
          isFiltered={isFiltered}
          renderStackedRow={(product) => (
            <div className="flex flex-col gap-1 p-4">
              <div className="flex items-center gap-2">
                <Link href={hrefFor(product)} className="font-medium after:absolute after:inset-0">
                  {product.sku}
                </Link>
                {canSeeStock ? <HealthBadge health={product.health} onHand={product.on_hand} /> : null}
              </div>
              <p className="text-body">{product.name}</p>
              <p className="text-sm text-muted-foreground">
                <Money value={product.unit_price} />
                {canSeeStock ? ` · ${formatQuantity(product.available)} available` : ""}
                {product.supplier ? ` · ${product.supplier.name}` : ""}
              </p>
            </div>
          )}
          noResults={
            <EmptyState
              icon={SearchX}
              title="No products match these filters"
              action={
                <Button type="button" variant="secondary" onClick={clearAll}>
                  Clear filters
                </Button>
              }
            />
          }
          empty={<EmptyState icon={Tag} title="No products yet" description="Import products.csv to create your catalog. SKUs are matched exactly." />}
        />
        {list.data && total > 0 ? (
          <Pagination
            page={params.page}
            pageSize={params.page_size}
            total={total}
            onPageChange={(page) => update({ page }, "push")}
            onPageSizeChange={(page_size) => update({ page_size })}
          />
        ) : null}
      </section>
    </div>
  );
}
