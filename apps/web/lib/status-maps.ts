import type { Schema } from "@retailops/contracts";
import {
  ArrowDownRight,
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
