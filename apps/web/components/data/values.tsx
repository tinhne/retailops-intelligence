"use client";

import { AlarmClock } from "lucide-react";

import { formatDateTime, formatDateTimeCompact, formatDue } from "@/lib/format/datetime";
import { formatMoney, formatMoneyForSpeech } from "@/lib/format/number";
import { useNow } from "@/lib/hooks/use-now";
import { useStore } from "@/lib/store/store-context";
import { cn } from "@/lib/utils";

/** Em dash for a missing value, announced as "None" (DESIGN_SYSTEM §11.2). */
export function NoValue() {
  return (
    <span aria-label="None" className="text-muted-foreground">
      —
    </span>
  );
}

/** Money in the store currency (C-01). `suffix` adds wording such as "at risk". */
export function Money({ value, suffix }: { value: string | null; suffix?: string }) {
  const { currency } = useStore();
  if (value === null) return <NoValue />;
  const text = formatMoney(value, currency);
  const spoken = formatMoneyForSpeech(value, currency);
  return (
    <span aria-label={spoken === text ? undefined : `${spoken}${suffix ? ` ${suffix}` : ""}`} className="tabular-nums">
      {text}
      {suffix ? ` ${suffix}` : null}
    </span>
  );
}

/** A timestamp in the store zone with its abbreviation (C-04). `compact` drops today's date. */
export function DateTime({ value, compact = false }: { value: string; compact?: boolean }) {
  const { timezone } = useStore();
  const now = useNow();
  const full = formatDateTime(value, timezone, now);
  return (
    <time dateTime={value} title={full}>
      {compact ? formatDateTimeCompact(value, timezone, now) : full}
    </time>
  );
}

/** "Due in 3h 55m" or alarm clock plus "Overdue 2h" (C-05). Re-renders every minute. */
export function DueLabel({ dueAt, className }: { dueAt: string; className?: string }) {
  const { timezone } = useStore();
  const now = useNow();
  const due = formatDue(dueAt, now);
  return (
    <time
      dateTime={dueAt}
      title={formatDateTime(dueAt, timezone, now)}
      className={cn("inline-flex items-center gap-1 whitespace-nowrap", due.overdue && "text-overdue", className)}
    >
      {due.overdue ? <AlarmClock aria-hidden className="size-3.5" /> : null}
      {due.text}
    </time>
  );
}
