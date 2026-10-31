import type { Schema } from "@retailops/contracts";

import { apiFetch, type QueryParams } from "./client";

export type ProductListItem = Schema<"ProductListItem">;
export type ProductDetail = Schema<"ProductDetail">;
export type Estimate = Schema<"Estimate">;
export type Movement = Schema<"MovementOut">;

/** Catalog and stock are read-only in the UI: they change through CSV imports (S-07..S-10). */
export const inventoryApi = {
  products: (storeId: string, query: QueryParams, signal?: AbortSignal) =>
    apiFetch<Schema<"Page_ProductListItem_">>(`/stores/${storeId}/products`, { query, signal }),
  product: (storeId: string, productId: string, signal?: AbortSignal) =>
    apiFetch<ProductDetail>(`/stores/${storeId}/products/${productId}`, { signal }),
  positions: (storeId: string, query: QueryParams, signal?: AbortSignal) =>
    apiFetch<Schema<"Page_InventoryPositionOut_">>(`/stores/${storeId}/inventory/positions`, { query, signal }),
  movements: (storeId: string, query: QueryParams, signal?: AbortSignal) =>
    apiFetch<Schema<"Page_MovementOut_">>(`/stores/${storeId}/inventory/movements`, { query, signal }),
  categories: (storeId: string, signal?: AbortSignal) => apiFetch<Schema<"CategoryList">>(`/stores/${storeId}/categories`, { signal }),
  suppliers: (storeId: string, signal?: AbortSignal) =>
    apiFetch<Schema<"Page_SupplierOut_">>(`/stores/${storeId}/suppliers`, { query: { page_size: 100, sort: "name" }, signal }),
};

export const inventoryKeys = {
  products: (storeId: string, query: QueryParams) => ["store", storeId, "products", query] as const,
  product: (storeId: string, productId: string) => ["store", storeId, "products", "detail", productId] as const,
  positions: (storeId: string, query: QueryParams) => ["store", storeId, "inventory", "positions", query] as const,
  movements: (storeId: string, query: QueryParams) => ["store", storeId, "inventory", "movements", query] as const,
  categories: (storeId: string) => ["store", storeId, "categories"] as const,
  suppliers: (storeId: string) => ["store", storeId, "suppliers"] as const,
};
