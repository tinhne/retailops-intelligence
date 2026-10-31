import type { Schema } from "@retailops/contracts";

import { apiFetch, type QueryParams } from "./client";

export type OrderListItem = Schema<"OrderListItem">;
export type OrderDetail = Schema<"OrderDetail">;
export type OrderLine = Schema<"OrderLineOut">;
export type OrderEvent = Schema<"OrderEventOut">;
export type LinkedException = Schema<"LinkedException">;
export type InventoryPosition = Schema<"InventoryPositionOut">;
export type StoreDetail = Schema<"StoreDetailOut">;

/** Orders are read-only in the UI: they change through CSV imports only (S-05). */
export const ordersApi = {
  list: (storeId: string, query: QueryParams, signal?: AbortSignal) =>
    apiFetch<Schema<"Page_OrderListItem_">>(`/stores/${storeId}/orders`, { query, signal }),
  detail: (storeId: string, orderId: string, signal?: AbortSignal) =>
    apiFetch<OrderDetail>(`/stores/${storeId}/orders/${orderId}`, { signal }),
  positions: (storeId: string, query: QueryParams, signal?: AbortSignal) =>
    apiFetch<Schema<"Page_InventoryPositionOut_">>(`/stores/${storeId}/inventory/positions`, { query, signal }),
  store: (storeId: string, signal?: AbortSignal) => apiFetch<StoreDetail>(`/stores/${storeId}`, { signal }),
};

export const orderKeys = {
  list: (storeId: string, query: QueryParams) => ["store", storeId, "orders", query] as const,
  detail: (storeId: string, orderId: string) => ["store", storeId, "orders", "detail", orderId] as const,
  position: (storeId: string, sku: string) => ["store", storeId, "inventory", "position", sku] as const,
  store: (storeId: string) => ["store", storeId, "detail"] as const,
};
