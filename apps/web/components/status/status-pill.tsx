import type { LucideIcon } from "lucide-react";

import {
  displayHealth,
  displayHealthMeta,
  exceptionStatusMeta,
  fulfillmentStatusMeta,
  orderStatusMeta,
  paymentStatusMeta,
  importStatusMeta,
  priorityBandLabels,
  resolvedMeta,
  severityMeta,
  toneClasses,
  type ExceptionStatus,
  type FulfillmentStatus,
  type ImportStatus,
  type OrderStatus,
  type PaymentStatus,
  type StockHealth,
  type PriorityBand,
  type ResolutionCode,
  type Severity,
  type Tone,
} from "@/lib/status-maps";
import { cn } from "@/lib/utils";

type StatusPillProps = {
  tone: Tone;
  label: string;
  icon?: LucideIcon;
  size?: "sm" | "md";
  /** Visually hidden prefix naming the dimension, e.g. "Severity:" (DESIGN_SYSTEM §12). */
  srPrefix?: string;
  className?: string;
};

/** The one pill implementation (C-09). Never interactive; the label is always present. */
export function StatusPill({ tone, label, icon: Icon, size = "sm", srPrefix, className }: StatusPillProps) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center gap-1 rounded-sm border text-xs whitespace-nowrap",
        size === "sm" ? "h-5 px-1.5" : "h-6 px-2",
        toneClasses[tone],
        className,
      )}
    >
      {Icon ? <Icon aria-hidden className={size === "sm" ? "size-3" : "size-3.5"} /> : null}
      {srPrefix ? <span className="sr-only">{srPrefix} </span> : null}
      {label}
    </span>
  );
}

export function SeverityBadge({ severity, size }: { severity: Severity; size?: "sm" | "md" }) {
  const meta = severityMeta[severity];
  return <StatusPill tone={meta.tone} label={meta.label} icon={meta.icon} size={size} srPrefix="Severity:" />;
}

export function ExceptionStatusPill({
  status,
  resolutionCode,
  verifiedAt,
  size,
}: {
  status: ExceptionStatus;
  resolutionCode?: ResolutionCode | null;
  verifiedAt?: string | null;
  size?: "sm" | "md";
}) {
  const meta = status === "RESOLVED" ? resolvedMeta(resolutionCode, verifiedAt) : exceptionStatusMeta[status];
  return <StatusPill tone={meta.tone} label={meta.label} icon={meta.icon} size={size} srPrefix="Status:" />;
}

export function ImportStatusPill({ status, size }: { status: ImportStatus; size?: "sm" | "md" }) {
  const meta = importStatusMeta[status];
  return <StatusPill tone={meta.tone} label={meta.label} icon={meta.icon} size={size} srPrefix="Import status:" />;
}

const barClasses: Record<PriorityBand, { bar: string; text: string }> = {
  P1: { bar: "bg-priority-p1-bar", text: "text-priority-p1" },
  P2: { bar: "bg-priority-p2-bar", text: "text-priority-p2" },
  P3: { bar: "bg-priority-p3-bar", text: "text-priority-p3" },
  P4: { bar: "bg-priority-p4-bar", text: "text-priority-p4" },
};

/** Meter plus "P1 · 81": a different shape from severity pills, so the two never blur (C-12). */
export function PriorityIndicator({ band, score }: { band: PriorityBand; score: number }) {
  const filled = priorityBandLabels[band].filledBars;
  return (
    <span className="inline-flex shrink-0 items-center gap-1.5" aria-label={`Priority ${band}, score ${score} of 100`} role="img">
      <span aria-hidden className="flex items-end gap-0.5">
        {[0, 1, 2, 3].map((index) => (
          <span
            key={index}
            className={cn("h-2.5 w-[3px] rounded-[1px]", index < filled ? barClasses[band].bar : "bg-priority-bar-empty")}
          />
        ))}
      </span>
      <span aria-hidden className={cn("text-body-strong tabular-nums", barClasses[band].text)}>
        {band} · {score}
      </span>
    </span>
  );
}

export function OrderStatusPill({ status, size }: { status: OrderStatus; size?: "sm" | "md" }) {
  const meta = orderStatusMeta[status];
  return <StatusPill tone={meta.tone} label={meta.label} icon={meta.icon} size={size} srPrefix="Order status:" />;
}

const axisText: Record<Tone, string> = {
  neutral: "text-tone-neutral-fg",
  outline: "text-tone-outline-fg",
  muted: "text-tone-muted-fg",
  primary: "text-tone-primary-fg",
  info: "text-tone-info-fg",
  success: "text-tone-success-fg",
  warning: "text-tone-warning-fg",
  caution: "text-tone-caution-fg",
  attention: "text-tone-attention-fg",
  danger: "text-tone-danger-fg",
  "danger-solid": "text-tone-danger-fg",
};

/** Payment or fulfillment status as icon plus coloured text, for table cells (C-14). */
export function AxisText({ axis, value }: { axis: "payment"; value: PaymentStatus } | { axis: "fulfillment"; value: FulfillmentStatus }) {
  const meta = axis === "payment" ? paymentStatusMeta[value as PaymentStatus] : fulfillmentStatusMeta[value as FulfillmentStatus];
  const Icon = meta.icon;
  return (
    <span className={cn("inline-flex items-center gap-1 whitespace-nowrap", axisText[meta.tone])}>
      <Icon aria-hidden className="size-3.5" />
      <span className="sr-only">{axis === "payment" ? "Payment:" : "Fulfillment:"} </span>
      {meta.label}
    </span>
  );
}

/** Stock health, with negative on-hand shown as a data issue whatever the health says (C-13). */
export function HealthBadge({ health, onHand, size }: { health: StockHealth | null; onHand: number; size?: "sm" | "md" }) {
  const value = displayHealth(health, onHand);
  const meta = displayHealthMeta[value];
  const title =
    value === "DATA_ISSUE"
      ? `On hand is negative (${onHand}). That is physically impossible, so stock health can't be computed until a cycle count corrects it (BR-402a).`
      : meta.description;
  return (
    <span title={title}>
      <StatusPill tone={meta.tone} label={meta.label} icon={meta.icon} size={size} srPrefix="Stock:" />
    </span>
  );
}
