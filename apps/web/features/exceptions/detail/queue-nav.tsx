"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";

import { ActionButton } from "@/components/actions/action-button";
import { Button } from "@/components/ui/button";
import { formatQuantity } from "@/lib/format/number";
import { useStore } from "@/lib/store/store-context";

import { useQueueNeighbours } from "../queue";

/**
 * Previous / Next in queue (S-04 header): the neighbours of this exception on the list page the
 * person came from. Not rendered when they arrived some other way (a shared link, a notification).
 */
export function QueueNav({ exceptionId }: { exceptionId: string }) {
  const store = useStore();
  const queue = useQueueNeighbours(store.id, exceptionId);
  if (!queue || queue.total < 2) return null;
  const href = (id: string) => `/s/${store.id}/exceptions/${id}`;

  return (
    <nav aria-label="Queue" className="flex items-center gap-2">
      <span className="text-sm text-muted-foreground tabular-nums">
        {formatQuantity(queue.position)} of {formatQuantity(queue.total)}
      </span>
      {queue.previous ? (
        <Button asChild variant="secondary" size="sm">
          <Link href={href(queue.previous.id)} aria-label={`Previous: ${queue.previous.reference}`}>
            <ChevronLeft aria-hidden />
            Previous
          </Link>
        </Button>
      ) : (
        <ActionButton gate={{ allowed: false, reason: "This is the first exception on that page of the list." }} variant="secondary" size="sm">
          <ChevronLeft aria-hidden />
          Previous
        </ActionButton>
      )}
      {queue.next ? (
        <Button asChild variant="secondary" size="sm">
          <Link href={href(queue.next.id)} aria-label={`Next in queue: ${queue.next.reference}`}>
            Next in queue
            <ChevronRight aria-hidden />
          </Link>
        </Button>
      ) : (
        <ActionButton gate={{ allowed: false, reason: "This is the last exception on that page of the list." }} variant="secondary" size="sm">
          Next in queue
          <ChevronRight aria-hidden />
        </ActionButton>
      )}
    </nav>
  );
}
