import type { Schema } from "@retailops/contracts";
import {
  ArrowDownRight,
  Ban,
  Clock,
  Database,
  Minus,
  Package,
  PackageCheck,
  Receipt,
  Truck,
  Undo2,
  Circle,
  CircleAlert,
  CircleCheck,
  CircleMinus,
  CirclePlay,
  CircleSlash,
  CircleX,
  CornerUpRight,
  Eye,
  FileCheck,
  FileX,
  Hourglass,
  Loader,
  OctagonAlert,
  PackageX,
  RotateCcw,
  TrendingDown,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react";

// The single source of UI labels, tones and icons for API enums (DESIGN_SYSTEM §3.5,
// COMPONENT_INVENTORY §3). Labels are never derived from enum strings at render time.

export type Tone =
  | "neutral"
  | "outline"
  | "muted"
  | "primary"
  | "info"
  | "success"
  | "warning"
  | "caution"
  | "attention"
  | "danger"
  | "danger-solid";

export type StatusMeta = { label: string; tone: Tone; icon: LucideIcon };

export type Severity = Schema<"Severity">;
export type ExceptionStatus = Schema<"ExceptionStatus">;
export type PriorityBand = Schema<"PriorityBand">;
export type ExceptionCategory = Schema<"ExceptionCategory">;
export type ResolutionCode = Schema<"ResolutionCode">;
export type StockHealth = Schema<"StockHealth">;
export type ImportStatus = Schema<"ImportStatus">;
export type ImportType = Schema<"ImportType">;
export type EvaluationStatus = Schema<"EvaluationStatus">;
export type EvaluationTrigger = Schema<"EvaluationTrigger">;

export const severityMeta: Record<Severity, StatusMeta> = {
  CRITICAL: { label: "Critical", tone: "danger-solid", icon: OctagonAlert },
  HIGH: { label: "High", tone: "attention", icon: TriangleAlert },
  MEDIUM: { label: "Medium", tone: "caution", icon: CircleAlert },
  LOW: { label: "Low", tone: "neutral", icon: CircleMinus },
};

export const exceptionStatusMeta: Record<Exclude<ExceptionStatus, "RESOLVED">, StatusMeta> = {
  OPEN: { label: "Open", tone: "outline", icon: Circle },
  ACKNOWLEDGED: { label: "Acknowledged", tone: "info", icon: Eye },
  IN_PROGRESS: { label: "In progress", tone: "primary", icon: CirclePlay },
  REOPENED: { label: "Reopened", tone: "warning", icon: RotateCcw },
  DISMISSED: { label: "Dismissed", tone: "muted", icon: CircleSlash },
};

/**
 * `RESOLVED` has four forms (DESIGN_SYSTEM §3.5). A manual resolution never shows a success tone
 * before `verified_at` exists, because the next evaluation may still reopen it.
 */
export function resolvedMeta(resolutionCode: ResolutionCode | null | undefined, verifiedAt: string | null | undefined): StatusMeta {
  if (resolutionCode === "SUPERSEDED") return { label: "Superseded", tone: "muted", icon: CornerUpRight };
  if (resolutionCode === "CONDITION_CLEARED") {
    return { label: "Resolved · condition cleared", tone: "success", icon: CircleCheck };
  }
  if (verifiedAt) return { label: "Verified", tone: "success", icon: CircleCheck };
  return { label: "Resolved — awaiting verification", tone: "info", icon: Hourglass };
}

export const priorityBandLabels: Record<PriorityBand, { filledBars: number }> = {
  P1: { filledBars: 4 },
  P2: { filledBars: 3 },
  P3: { filledBars: 2 },
  P4: { filledBars: 1 },
};

export const categoryLabels: Record<ExceptionCategory, string> = {
  INVENTORY: "Inventory",
  FULFILLMENT: "Fulfillment",
  PAYMENT: "Payment",
  DATA_QUALITY: "Data quality",
};

export const stockHealthMeta: Record<StockHealth, StatusMeta> = {
  OVERSOLD: { label: "Oversold", tone: "danger-solid", icon: CircleX },
  OUT_OF_STOCK: { label: "Out of stock", tone: "danger", icon: PackageX },
  BELOW_REORDER_POINT: { label: "Below reorder point", tone: "warning", icon: TrendingDown },
  APPROACHING_REORDER_POINT: { label: "Approaching reorder point", tone: "caution", icon: ArrowDownRight },
  HEALTHY: { label: "Healthy", tone: "success", icon: CircleCheck },
  DATA_ISSUE: { label: "Data issue", tone: "attention", icon: Database },
};

/**
 * Display order for filters, summary bars and the dashboard card: the availability classes from
 * worst to best, then the data issue, which is not an availability class (BR-402a, S-02, S-09).
 */
export const STOCK_HEALTH_ORDER: StockHealth[] = [
  "OVERSOLD",
  "OUT_OF_STOCK",
  "BELOW_REORDER_POINT",
  "APPROACHING_REORDER_POINT",
  "HEALTHY",
  "DATA_ISSUE",
];

export type InventoryHealthSummary = Schema<"InventoryHealthSummary">;

/** Where each class is counted in the dashboard's `inventory` summary (ACTIVE products). */
export const stockHealthSummaryKey: Record<StockHealth, Exclude<keyof InventoryHealthSummary, "active_products">> = {
  OVERSOLD: "oversold",
  OUT_OF_STOCK: "out_of_stock",
  BELOW_REORDER_POINT: "below_reorder_point",
  APPROACHING_REORDER_POINT: "approaching_reorder_point",
  HEALTHY: "healthy",
  DATA_ISSUE: "data_issue",
};

export const importStatusMeta: Record<ImportStatus, StatusMeta> = {
  UPLOADED: { label: "Validating", tone: "neutral", icon: Loader },
  VALIDATING: { label: "Validating", tone: "neutral", icon: Loader },
  VALIDATED: { label: "Ready to apply", tone: "info", icon: FileCheck },
  APPLYING: { label: "Applying", tone: "info", icon: Loader },
  COMPLETED: { label: "Completed", tone: "success", icon: CircleCheck },
  COMPLETED_WITH_ERRORS: { label: "Completed, rows skipped", tone: "warning", icon: CircleAlert },
  FAILED: { label: "Failed", tone: "danger", icon: CircleX },
  REJECTED: { label: "Rejected", tone: "danger", icon: FileX },
  DISCARDED: { label: "Discarded", tone: "muted", icon: CircleSlash },
};

export const importTypeLabels: Record<ImportType, string> = {
  products: "Products",
  orders: "Orders",
  order_items: "Order items",
  inventory_adjustments: "Inventory adjustments",
};

export const evaluationTriggerLabels: Record<EvaluationTrigger, string> = {
  MANUAL: "Manual",
  IMPORT: "After import",
  SCHEDULED: "Scheduled",
};

export const evaluationStatusLabels: Record<EvaluationStatus, string> = {
  RUNNING: "Running",
  SUCCEEDED: "Succeeded",
  FAILED: "Failed",
  SKIPPED: "Skipped",
};

/** Tailwind classes per tone (tested fg/bg/border pairs, DESIGN_SYSTEM §20). */
export const toneClasses: Record<Tone, string> = {
  neutral: "border-tone-neutral-border bg-tone-neutral-bg text-tone-neutral-fg",
  outline: "border-tone-outline-border bg-tone-outline-bg text-tone-outline-fg",
  muted: "border-tone-muted-border bg-tone-muted-bg text-tone-muted-fg",
  primary: "border-tone-primary-border bg-tone-primary-bg text-tone-primary-fg",
  info: "border-tone-info-border bg-tone-info-bg text-tone-info-fg",
  success: "border-tone-success-border bg-tone-success-bg text-tone-success-fg",
  warning: "border-tone-warning-border bg-tone-warning-bg text-tone-warning-fg",
  caution: "border-tone-caution-border bg-tone-caution-bg text-tone-caution-fg",
  attention: "border-tone-attention-border bg-tone-attention-bg text-tone-attention-fg",
  danger: "border-tone-danger-border bg-tone-danger-bg text-tone-danger-fg",
  "danger-solid": "border-tone-danger-solid-border bg-tone-danger-solid-bg text-tone-danger-solid-fg",
};

export type ExceptionType = Schema<"ExceptionType">;
export type ManualResolutionCode = Schema<"ManualResolutionCode">;
export type DismissalReason = Schema<"DismissalReason">;

/** Short labels for the nine catalog rules (EXCEPTION_CATALOG, S-03 Type filter). */
export const exceptionTypeLabels: Record<ExceptionType, string> = {
  INVENTORY_OVERSOLD: "Oversold",
  INVENTORY_OVERSELL_RISK: "Oversell risk",
  INVENTORY_OUT_OF_STOCK: "Out of stock",
  INVENTORY_BELOW_REORDER_POINT: "Below reorder point",
  ORDER_FULFILLMENT_OVERDUE: "Fulfillment overdue",
  ORDER_STALLED_AFTER_PAYMENT: "Stalled after payment",
  ORDER_REFUND_PENDING: "Refund pending",
  DATA_ORDER_TOTAL_MISMATCH: "Order total mismatch",
  DATA_NEGATIVE_ON_HAND: "Negative on-hand",
};

export const exceptionTypeCategory: Record<ExceptionType, ExceptionCategory> = {
  INVENTORY_OVERSOLD: "INVENTORY",
  INVENTORY_OVERSELL_RISK: "INVENTORY",
  INVENTORY_OUT_OF_STOCK: "INVENTORY",
  INVENTORY_BELOW_REORDER_POINT: "INVENTORY",
  ORDER_FULFILLMENT_OVERDUE: "FULFILLMENT",
  ORDER_STALLED_AFTER_PAYMENT: "FULFILLMENT",
  ORDER_REFUND_PENDING: "PAYMENT",
  DATA_ORDER_TOTAL_MISMATCH: "DATA_QUALITY",
  DATA_NEGATIVE_ON_HAND: "DATA_QUALITY",
};

/** The codes a person may choose when resolving (STATE_MACHINES §3.2). */
export const manualResolutionLabels: Record<ManualResolutionCode, string> = {
  STOCK_REPLENISHED: "Stock replenished",
  ORDER_FULFILLED: "Order fulfilled",
  REFUND_ISSUED: "Refund issued",
  DATA_CORRECTED: "Data corrected",
  CUSTOMER_CONTACTED: "Customer contacted",
  FIXED_IN_SOURCE_SYSTEM: "Fixed in source system",
  OTHER: "Other",
};

export const resolutionCodeLabels: Record<ResolutionCode, string> = {
  ...manualResolutionLabels,
  CONDITION_CLEARED: "Condition cleared",
  SUPERSEDED: "Superseded",
};

export const dismissalReasonLabels: Record<DismissalReason, { label: string; description: string }> = {
  FALSE_POSITIVE: { label: "False positive", description: "The condition isn't real" },
  ACCEPTED_RISK: { label: "Accepted risk", description: "We know and accept it" },
  DUPLICATE: { label: "Duplicate", description: "Tracked elsewhere" },
  NOT_ACTIONABLE: { label: "Not actionable", description: "Nothing we can do" },
};

/** Labels for any exception status in prose ("changed status from Open to In progress"). */
export const exceptionStatusLabels: Record<ExceptionStatus, string> = {
  OPEN: "Open",
  ACKNOWLEDGED: "Acknowledged",
  IN_PROGRESS: "In progress",
  REOPENED: "Reopened",
  RESOLVED: "Resolved",
  DISMISSED: "Dismissed",
};

export type OrderStatus = Schema<"OrderStatus">;
export type PaymentStatus = Schema<"PaymentStatus">;
export type FulfillmentStatus = Schema<"FulfillmentStatus">;
export type SalesChannel = Schema<"SalesChannel">;
export type ChangeSource = Schema<"ChangeSource">;
export type ReservationStatus = Schema<"ReservationStatus">;

/** Order lifecycle, toned by status group (DESIGN_SYSTEM §3.5, STATE_MACHINES §1). */
export const orderStatusMeta: Record<OrderStatus, StatusMeta> = {
  CREATED: { label: "Created", tone: "neutral", icon: Clock },
  PAYMENT_PENDING: { label: "Payment pending", tone: "neutral", icon: Clock },
  PAYMENT_FAILED: { label: "Payment failed", tone: "danger", icon: CircleX },
  PAID: { label: "Paid", tone: "info", icon: Package },
  PROCESSING: { label: "Processing", tone: "info", icon: Package },
  READY_TO_SHIP: { label: "Ready to ship", tone: "info", icon: Package },
  SHIPPED: { label: "Shipped", tone: "success", icon: Truck },
  DELIVERED: { label: "Delivered", tone: "success", icon: PackageCheck },
  RETURN_REQUESTED: { label: "Return requested", tone: "warning", icon: Undo2 },
  RETURNED: { label: "Returned", tone: "warning", icon: Undo2 },
  CANCELLED: { label: "Cancelled", tone: "outline", icon: Ban },
  REFUNDED: { label: "Refunded", tone: "outline", icon: Receipt },
};

export const paymentStatusMeta: Record<PaymentStatus, StatusMeta> = {
  PENDING: { label: "Pending", tone: "neutral", icon: Clock },
  PAID: { label: "Paid", tone: "success", icon: CircleCheck },
  FAILED: { label: "Failed", tone: "danger", icon: CircleX },
  REFUNDED: { label: "Refunded", tone: "muted", icon: Receipt },
};

export const fulfillmentStatusMeta: Record<FulfillmentStatus, StatusMeta> = {
  UNFULFILLED: { label: "Unfulfilled", tone: "neutral", icon: Circle },
  IN_PROGRESS: { label: "In progress", tone: "info", icon: Package },
  SHIPPED: { label: "Shipped", tone: "success", icon: Truck },
  DELIVERED: { label: "Delivered", tone: "success", icon: PackageCheck },
  RETURNED: { label: "Returned", tone: "warning", icon: Undo2 },
};

export const channelLabels: Record<SalesChannel, string> = {
  WEB: "Web",
  MARKETPLACE: "Marketplace",
  POS: "POS",
  OTHER: "Other",
};

export const changeSourceLabels: Record<ChangeSource, string> = { IMPORT: "Import", USER: "User", SYSTEM: "System" };

export const reservationLabels: Record<ReservationStatus, string> = {
  ACTIVE: "Reserved",
  CONSUMED: "Shipped",
  RELEASED: "Released",
};

/** Health shown to people: the API value, or "Not tracked" when the API leaves it null. */
export type DisplayHealth = StockHealth | "NOT_TRACKED";

export const displayHealthMeta: Record<DisplayHealth, StatusMeta & { description?: string }> = {
  ...stockHealthMeta,
  DATA_ISSUE: {
    ...stockHealthMeta.DATA_ISSUE,
    description: "On hand is negative, which is physically impossible, so stock health can't be computed until a cycle count corrects it (BR-402a).",
  },
  NOT_TRACKED: { label: "Not tracked", tone: "muted", icon: Minus, description: "Stock health is computed for active products only." },
};

/**
 * The API classifies negative on-hand as `DATA_ISSUE` for any product status (BR-402a), and
 * returns null only for inactive products with valid stock.
 */
export function displayHealth(health: StockHealth | null): DisplayHealth {
  return health ?? "NOT_TRACKED";
}

export type ProductStatus = Schema<"ProductStatus">;
export type MovementType = Schema<"MovementType">;
export type MovementSource = Schema<"MovementSource">;

/** Product status is a tag, not a state colour (S-07): Active neutral, Draft outline, Archived muted. */
export const productStatusMeta: Record<ProductStatus, { label: string; tone: Tone }> = {
  ACTIVE: { label: "Active", tone: "neutral" },
  DRAFT: { label: "Draft", tone: "outline" },
  ARCHIVED: { label: "Archived", tone: "muted" },
};

export const movementTypeLabels: Record<MovementType, string> = {
  CYCLE_COUNT: "Cycle count",
  RECEIPT: "Receipt",
  INCOMING_EXPECTED: "Incoming expected",
  INCOMING_CANCELLED: "Incoming cancelled",
  DAMAGE: "Damage",
  SHRINKAGE: "Shrinkage",
  RETURN_RESTOCK: "Return restock",
  CORRECTION: "Correction",
  SHIPMENT: "Shipment",
};

export const movementSourceLabels: Record<MovementSource, string> = { IMPORT: "Import", ORDER: "Order", SYSTEM: "System" };

export type ImportMode = Schema<"ImportMode">;
export type RowAction = Schema<"RowAction">;

/** The recommended order: each file references the ones before it (IMPORT_PIPELINE §10). */
export const IMPORT_TYPES_IN_ORDER: ImportType[] = ["products", "inventory_adjustments", "orders", "order_items"];

export const importModeLabels: Record<ImportMode, string> = { STRICT: "Strict", VALID_ROWS_ONLY: "Valid rows only" };

export const rowActionLabels: Record<RowAction, string> = {
  CREATE: "Create",
  UPDATE: "Update",
  UNCHANGED: "Unchanged",
  SKIP: "Has errors",
};

type IssueLevel = "FILE" | "ERROR" | "WARNING";

/**
 * Issue codes with their "How to fix" text, mirrored from IMPORT_PIPELINE §6. The API message
 * says what went wrong; this adds what to do. An unknown code falls back to the message alone.
 */
export const importIssueMeta: Record<string, { level: IssueLevel; fix: string }> = {
  FILE_EMPTY: { level: "FILE", fix: "Re-export, and check that the export filter returned rows." },
  FILE_TOO_LARGE: { level: "FILE", fix: "Split the file by date range and import the parts in order." },
  FILE_TYPE: { level: "FILE", fix: "Save or export the file as CSV." },
  FILE_ENCODING: { level: "FILE", fix: "Save the file as \"CSV UTF-8\"." },
  TOO_MANY_ROWS: { level: "FILE", fix: "Split the file into parts of at most 20,000 rows." },
  TOO_MANY_COLUMNS: { level: "FILE", fix: "Keep only the template's columns; a file may have at most 100." },
  MISSING_COLUMNS: { level: "FILE", fix: "Start from the downloadable template, or choose the right import type." },
  REQUIRED: { level: "ERROR", fix: "Fill in the value in the source export." },
  VALUE_TOO_LONG: { level: "ERROR", fix: "Shorten the value in the source." },
  INVALID_ENUM: { level: "ERROR", fix: "Map the source value to one of the allowed values." },
  INVALID_NUMBER: { level: "ERROR", fix: "Remove currency symbols and thousands separators, and round to cents." },
  INVALID_INTEGER: { level: "ERROR", fix: "Use a whole number in the allowed range." },
  NEGATIVE_VALUE: { level: "ERROR", fix: "Use the positive amount; the type gives the sign. Use CORRECTION for a signed fix." },
  INVALID_DATETIME: { level: "ERROR", fix: "Export timestamps as ISO-8601, for example 2026-11-05T14:00:00-05:00." },
  DUPLICATE_KEY_IN_FILE: { level: "ERROR", fix: "Remove the repeated row or merge the rows." },
  UNKNOWN_SKU: { level: "ERROR", fix: "Import the product first, or fix the SKU's spelling and case." },
  UNKNOWN_ORDER: { level: "ERROR", fix: "Import orders.csv first." },
  CURRENCY_MISMATCH: { level: "ERROR", fix: "Export in the store currency; multi-currency isn't supported." },
  ORDER_INVALID_STATUS_COMBINATION: { level: "ERROR", fix: "Check how the source maps payment and fulfillment states." },
  ORDER_MISSING_TIMESTAMP: { level: "ERROR", fix: "Include paid_at, shipped_at, delivered_at or cancelled_at as the statuses require." },
  ORDER_TIMESTAMP_SEQUENCE: { level: "ERROR", fix: "Usually a time-zone mix-up between columns; check the offsets." },
  ORDER_TRANSITION_NOT_ALLOWED: { level: "ERROR", fix: "Usually an older export; import the newest one. If the source really went backwards, fix it there." },
  ORDER_LINE_LOCKED: { level: "ERROR", fix: "Shipped lines are history; correct the source only if the shipment record itself was wrong." },
  LINE_DISCOUNT_EXCEEDS_LINE: { level: "ERROR", fix: "Check whether the source discount is per unit or per line." },
  STALE_CYCLE_COUNT: { level: "ERROR", fix: "Usually a re-sent old count. Drop the row; if the old count was wrong, record a CORRECTION." },
  UNKNOWN_COLUMN: { level: "WARNING", fix: "Nothing to do, or remove the column." },
  TIMEZONE_ASSUMED: { level: "WARNING", fix: "Export with UTC offsets to remove the ambiguity." },
  PRICE_ZERO: { level: "WARNING", fix: "Confirm it is intentional, for example a free sample." },
  NEGATIVE_MARGIN: { level: "WARNING", fix: "Confirm the cost or the price." },
  ALREADY_APPLIED: { level: "WARNING", fix: "Nothing to do. Use a new reference for a genuinely new movement." },
  DUPLICATE_FILE: { level: "WARNING", fix: "Check that you meant to import it again; applying it is safe." },
};

export type ToolCallStatus = Schema<"ToolCallStatus">;

/** Human labels for the copilot's read-only tools (docs/ai/TOOL_CATALOG.md). */
export const copilotToolLabels: Record<string, string> = {
  list_exceptions: "Exceptions list",
  get_exception: "Exception detail",
  get_exception_history: "Exception history",
  get_related_orders: "Related orders",
  get_overdue_orders: "Overdue orders",
  get_product: "Product",
  get_inventory_position: "Inventory position",
  get_inventory_movements: "Inventory movements",
  get_dashboard_summary: "Dashboard summary",
  get_import_errors: "Import errors",
  get_operational_trends: "Operational trends",
};

export const toolCallStatusLabels: Record<ToolCallStatus, string> = {
  SUCCESS: "OK",
  INVALID_ARGUMENTS: "Invalid arguments",
  PERMISSION_DENIED: "Not available to your role",
  NOT_FOUND: "Not found",
  TIMEOUT: "Timed out",
  REJECTED_LIMIT: "Over the size limit",
  UNKNOWN_TOOL: "Unknown tool",
  ERROR: "Failed",
};
