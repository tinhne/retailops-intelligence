"use client";

import { Info } from "lucide-react";
import Link from "next/link";

import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

type KpiCardProps = {
  label: string;
  value: React.ReactNode;
  secondary?: React.ReactNode;
  /** Present only when the list behind the number exists and may be opened. */
  href?: string;
  /** Definition shown in a tooltip from a separate, focusable button. */
  info?: string;
};

/**
 * One headline number (COMPONENT_INVENTORY C-39). A link card is a single `<a>` whose name
 * combines label, value and secondary text. No count-up animation.
 */
export function KpiCard({ label, value, secondary, href, info }: KpiCardProps) {
  const body = (
    <>
      <span className={cn("text-sm text-muted-foreground", info && "pr-6")}>{label}</span>
      <span className="text-display">{value}</span>
      {secondary ? <span className="text-sm text-muted-foreground">{secondary}</span> : null}
    </>
  );

  return (
    <div
      className={cn(
        "relative flex min-h-[120px] flex-col rounded-lg border bg-card p-4 md:p-5",
        href && "transition-colors duration-100 hover:bg-surface-hover",
      )}
    >
      {href ? (
        <Link
          href={href}
          className="flex flex-1 flex-col gap-1 rounded-md outline-offset-4 after:absolute after:inset-0 after:rounded-lg"
        >
          {body}
        </Link>
      ) : (
        <div className="flex flex-1 flex-col gap-1">{body}</div>
      )}
      {info ? (
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              aria-label={`About ${label}`}
              className="absolute top-3 right-3 z-[1] inline-flex size-6 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground"
            >
              <Info aria-hidden className="size-4" />
            </button>
          </TooltipTrigger>
          <TooltipContent>{info}</TooltipContent>
        </Tooltip>
      ) : null}
    </div>
  );
}

export function KpiSkeleton() {
  return (
    <div className={cn("flex min-h-[120px] flex-col gap-2 rounded-lg border bg-card p-4 md:p-5")}>
      <Skeleton className="h-4 w-24" />
      <Skeleton className="h-8 w-16" />
      <Skeleton className="h-4 w-28" />
    </div>
  );
}
