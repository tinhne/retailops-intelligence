import type { QueryParams } from "@/lib/api/client";
import { parseRange, rangeToApi } from "@/lib/date-range";
import { storeMidnight } from "@/lib/format/datetime";
import type { FulfillmentStatus, OrderStatus, PaymentStatus, SalesChannel } from "@/lib/status-maps";

// URL state for the orders list (S-05, IA §9), parsed and validated like the exceptions inbox.

export const ORDER_STATUSES: OrderStatus[] = [
  "CREATED",
  "PAYMENT_PENDING",
  "PAYMENT_FAILED",
  "PAID",
  "PROCESSING",
  "READY_TO_SHIP",
  "SHIPPED",
  "DELIVERED",
  "RETURN_REQUESTED",
  "RETURNED",
  "CANCELLED",
  "REFUNDED",
];
export const PAYMENT_STATUSES: PaymentStatus[] = ["PENDING", "PAID", "FAILED", "REFUNDED"];
export const FULFILLMENT_STATUSES: FulfillmentStatus[] = ["UNFULFILLED", "IN_PROGRESS", "SHIPPED", "DELIVERED", "RETURNED"];
export const CHANNELS: SalesChannel[] = ["WEB", "MARKETPLACE", "POS", "OTHER"];
export const ORDER_SORTS = ["-placed_at", "placed_at", "ship_by", "-total", "order_number"] as const;
export type OrderSort = (typeof ORDER_SORTS)[number];
export const PLACED = ["today", "7d", "30d", "60d", "custom"] as const;
export type Placed = (typeof PLACED)[number];
const PAGE_SIZES = [25, 50, 100] as const;

/** Status groups for the Status filter (DESIGN_SYSTEM §3.5). */
export const STATUS_GROUPS: Record<OrderStatus, string> = {
  CREATED: "Awaiting payment",
  PAYMENT_PENDING: "Awaiting payment",
  PAYMENT_FAILED: "Payment failed",
  PAID: "To fulfil",
  PROCESSING: "To fulfil",
  READY_TO_SHIP: "To fulfil",
  SHIPPED: "Fulfilled",
  DELIVERED: "Fulfilled",
  RETURN_REQUESTED: "Returns",
  RETURNED: "Returns",
  CANCELLED: "Closed",
  REFUNDED: "Closed",
};

export type OrderParams = {
  q: string;
  status: OrderStatus[];
  payment_status: PaymentStatus | null;
  fulfillment_status: FulfillmentStatus | null;
  channel: SalesChannel | null;
  placed: Placed | null;
  /** Store-local days (`YYYY-MM-DD`) of a custom range; only used when `placed` is "custom". */
  placed_from: string | null;
  placed_to: string | null;
  overdue: boolean;
  sort: OrderSort;
  page: number;
  page_size: 25 | 50 | 100;
};

function one<T extends string>(value: string | null, allowed: readonly T[], invalid: string[], key: string): T | null {
  if (value === null || value === "") return null;
  if ((allowed as readonly string[]).includes(value)) return value as T;
  invalid.push(key);
  return null;
}

export function parseOrderParams(search: URLSearchParams) {
  const invalid: string[] = [];
  const status: OrderStatus[] = [];
  for (const value of search.getAll("status")) {
    if ((ORDER_STATUSES as string[]).includes(value)) {
      if (!status.includes(value as OrderStatus)) status.push(value as OrderStatus);
    } else invalid.push("status");
  }
  const overdueRaw = search.get("overdue");
  if (overdueRaw !== null && overdueRaw !== "true") invalid.push("overdue");
  const page = Number(search.get("page") ?? "1");
  const pageSize = Number(search.get("page_size") ?? "25");
  if (search.has("page") && !(Number.isInteger(page) && page >= 1)) invalid.push("page");
  if (search.has("page_size") && !(PAGE_SIZES as readonly number[]).includes(pageSize)) invalid.push("page_size");
  const placed = one(search.get("placed"), PLACED, invalid, "placed");
  const range = parseRange(search, "placed_from", "placed_to", invalid);
  if (placed !== "custom" && (range.from || range.to)) invalid.push("placed_from");

  const params: OrderParams = {
    q: (search.get("q") ?? "").slice(0, 64),
    status,
    payment_status: one(search.get("payment_status"), PAYMENT_STATUSES, invalid, "payment_status"),
    fulfillment_status: one(search.get("fulfillment_status"), FULFILLMENT_STATUSES, invalid, "fulfillment_status"),
    channel: one(search.get("channel"), CHANNELS, invalid, "channel"),
    placed,
    placed_from: placed === "custom" ? range.from : null,
    placed_to: placed === "custom" ? range.to : null,
    overdue: overdueRaw === "true",
    sort: one(search.get("sort"), ORDER_SORTS, invalid, "sort") ?? "-placed_at",
    page: Number.isInteger(page) && page >= 1 ? page : 1,
    page_size: (PAGE_SIZES as readonly number[]).includes(pageSize) ? (pageSize as 25 | 50 | 100) : 25,
  };
  return { params, invalid };
}

export function serializeOrderParams(params: OrderParams): URLSearchParams {
  const search = new URLSearchParams();
  if (params.q) search.set("q", params.q);
  for (const value of params.status) search.append("status", value);
  if (params.payment_status) search.set("payment_status", params.payment_status);
  if (params.fulfillment_status) search.set("fulfillment_status", params.fulfillment_status);
  if (params.channel) search.set("channel", params.channel);
  if (params.placed) search.set("placed", params.placed);
  if (params.placed === "custom") {
    if (params.placed_from) search.set("placed_from", params.placed_from);
    if (params.placed_to) search.set("placed_to", params.placed_to);
  }
  if (params.overdue) search.set("overdue", "true");
  if (params.sort !== "-placed_at") search.set("sort", params.sort);
  if (params.page !== 1) search.set("page", String(params.page));
  if (params.page_size !== 25) search.set("page_size", String(params.page_size));
  return search;
}

const PRESET_DAYS: Record<Exclude<Placed, "custom">, number> = { today: 0, "7d": 6, "30d": 29, "60d": 59 };

/** `placed_from` (inclusive) and `placed_to` (exclusive) instants for a preset or a custom range. */
function placedWindow(params: OrderParams, now: Date, timeZone: string): { from?: string; to?: string } {
  if (!params.placed) return {};
  if (params.placed === "custom") return rangeToApi(params.placed_from, params.placed_to, timeZone);
  return { from: storeMidnight(now, timeZone, PRESET_DAYS[params.placed]).toISOString() };
}

export function toOrderQuery(params: OrderParams, now: Date, timeZone: string): QueryParams {
  const placed = placedWindow(params, now, timeZone);
  return {
    q: params.q.trim() || undefined,
    status: params.status,
    payment_status: params.payment_status ?? undefined,
    fulfillment_status: params.fulfillment_status ?? undefined,
    channel: params.channel ?? undefined,
    placed_from: placed.from,
    placed_to: placed.to,
    overdue: params.overdue ? true : undefined,
    sort: params.sort,
    page: params.page,
    page_size: params.page_size,
  };
}

export function isOrderFiltered(params: OrderParams): boolean {
  return Boolean(
    params.q.trim() ||
      params.status.length ||
      params.payment_status ||
      params.fulfillment_status ||
      params.channel ||
      (params.placed && (params.placed !== "custom" || params.placed_from || params.placed_to)) ||
      params.overdue,
  );
}

export function updateOrderParams(params: OrderParams, patch: Partial<OrderParams>): OrderParams {
  const next = { ...params, ...patch };
  if (!("page" in patch)) next.page = 1;
  if (next.placed !== "custom") {
    next.placed_from = null;
    next.placed_to = null;
  }
  return next;
}
