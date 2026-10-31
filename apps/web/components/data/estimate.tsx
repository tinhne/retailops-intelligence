"use client";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { Estimate } from "@/lib/api/inventory-api";

/**
 * An estimate with its "est." label (C-08, BR-152). The tooltip states the basis, so a projection
 * is never read as a fact. `null` renders the fallback text (BR-151: not enough history).
 */
export function EstimateValue({ estimate, unit, fallback = "Not enough sales history" }: { estimate: Estimate; unit?: string; fallback?: string }) {
  if (estimate.value === null) return <span className="text-sm text-muted-foreground">{fallback}</span>;
  const value = Number(estimate.value).toFixed(1);
  return (
    <span className="inline-flex items-baseline gap-1 tabular-nums">
      {value}
      {unit ? ` ${unit}` : null}
      <Tooltip>
        <TooltipTrigger asChild>
          <button type="button" className="rounded-sm text-xs font-normal text-muted-foreground underline decoration-dotted underline-offset-2">
            est.
          </button>
        </TooltipTrigger>
        <TooltipContent>
          Estimate based on the last {estimate.window_days} days of sales. It ignores seasonality and promotions (BR-152).
          {estimate.note ? ` ${estimate.note}.` : ""}
        </TooltipContent>
      </Tooltip>
    </span>
  );
}
