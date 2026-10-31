"use client";

import { useQuery } from "@tanstack/react-query";
import { CircleHelp } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { storeApi, storeKeys } from "@/lib/api/store-api";
import type { ExceptionListItem } from "@/lib/api/exceptions-api";
import { useStore } from "@/lib/store/store-context";

const STEPS = ["Open", "Acknowledged", "In progress", "Resolved — awaiting verification", "Verified"];
const AUTOMATIC = new Set(["CONDITION_CLEARED", "SUPERSEDED"]);

/** The first manually resolved exception that a later evaluation verified, if any. */
export function verifiedExample(items: ExceptionListItem[]): ExceptionListItem | undefined {
  return items.find((item) => item.verified_at !== null && item.resolution_code !== null && !AUTOMATIC.has(item.resolution_code));
}

/**
 * "How resolution works" (COMPONENT_INVENTORY C-63): for viewers, who see the lifecycle buttons
 * disabled, a plain explanation of the process with live examples from this store. Examples are
 * fetched when the popover opens and a link is left out when no example exists.
 */
export function LifecycleExplainer() {
  const store = useStore();
  const [open, setOpen] = useState(false);
  const resolvedQuery = { status: "RESOLVED", page_size: 25 };
  const reopenedQuery = { status: "REOPENED", page_size: 1 };
  const verified = useQuery({
    queryKey: storeKeys.exceptions(store.id, resolvedQuery),
    queryFn: ({ signal }) => storeApi.exceptions(store.id, resolvedQuery, signal),
    select: (page) => verifiedExample(page.items),
    enabled: open,
    staleTime: 5 * 60_000,
  });
  const reopened = useQuery({
    queryKey: storeKeys.exceptions(store.id, reopenedQuery),
    queryFn: ({ signal }) => storeApi.exceptions(store.id, reopenedQuery, signal),
    select: (page) => page.items[0],
    enabled: open,
    staleTime: 5 * 60_000,
  });
  const href = (id: string) => `/s/${store.id}/exceptions/${id}`;
  const loading = verified.isPending || reopened.isPending;
  const failed = verified.isError || reopened.isError;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button type="button" variant="ghost" size="sm">
          <CircleHelp aria-hidden />
          How resolution works
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 max-w-[calc(100vw-2rem)] text-sm">
        <h2 className="text-body-strong">How resolution works</h2>
        <ol className="mt-2 list-decimal space-y-0.5 pl-5">
          {STEPS.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
        <p className="mt-2 text-muted-foreground">
          A person resolves the exception, then RetailOps checks the condition again after the next import completes, or after 24 h. If
          it is gone, the exception is verified. If it is still present, the exception reopens instead (verification failed).
        </p>
        <p className="mt-2 text-muted-foreground">
          Exceptions also resolve on their own when an analysis finds the condition has cleared.
        </p>
        <div className="mt-3 flex flex-col gap-1 border-t pt-3" aria-live="polite">
          {loading ? (
            <p className="text-muted-foreground">Looking for examples in this store…</p>
          ) : failed ? (
            <p className="text-muted-foreground">Examples couldn&apos;t be loaded.</p>
          ) : verified.data || reopened.data ? (
            <>
              {verified.data ? (
                <Link href={href(verified.data.id)} className="text-link hover:underline">
                  A verified example: {verified.data.reference}
                </Link>
              ) : null}
              {reopened.data ? (
                <Link href={href(reopened.data.id)} className="text-link hover:underline">
                  A reopened example: {reopened.data.reference}
                </Link>
              ) : null}
            </>
          ) : (
            <p className="text-muted-foreground">This store has no verified or reopened exceptions to show yet.</p>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
