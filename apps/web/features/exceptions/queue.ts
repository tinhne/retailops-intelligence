"use client";

import { useSyncExternalStore } from "react";

// The work queue the person came from (S-04 "queue navigation"): the inbox remembers the rows of
// the page on screen, in order, and the investigation page offers the neighbours of the current
// exception. Kept per tab in sessionStorage, so it never leaks into another tab or session.

export const QUEUE_KEY = "ro.exceptions.queue";

export type QueueItem = { id: string; reference: string };
export type Queue = { listHref: string; items: QueueItem[] };

const listeners = new Set<() => void>();

export function saveQueue(queue: Queue) {
  try {
    window.sessionStorage.setItem(QUEUE_KEY, JSON.stringify(queue));
  } catch {
    // Storage unavailable: queue navigation is simply not offered.
  }
  listeners.forEach((listener) => listener());
}

function isQueue(value: unknown): value is Queue {
  if (typeof value !== "object" || value === null) return false;
  const queue = value as Partial<Queue>;
  return (
    typeof queue.listHref === "string" &&
    Array.isArray(queue.items) &&
    queue.items.every((item) => typeof item?.id === "string" && typeof item?.reference === "string")
  );
}

function readRaw(): string | null {
  try {
    return window.sessionStorage.getItem(QUEUE_KEY);
  } catch {
    return null;
  }
}

/** The remembered queue of this store, or `null` (no list visited in this tab, or another store). */
export function parseQueue(raw: string | null, storeId: string): Queue | null {
  if (!raw) return null;
  try {
    const value: unknown = JSON.parse(raw);
    return isQueue(value) && value.listHref.startsWith(`/s/${storeId}/exceptions`) ? value : null;
  } catch {
    return null;
  }
}

export type Neighbours = { previous?: QueueItem; next?: QueueItem; position: number; total: number };

/** Where `id` sits in the queue and its neighbours, or `null` when it is not part of it. */
export function neighbours(queue: Queue | null, id: string): Neighbours | null {
  if (!queue) return null;
  const index = queue.items.findIndex((item) => item.id === id);
  if (index < 0) return null;
  return { previous: queue.items[index - 1], next: queue.items[index + 1], position: index + 1, total: queue.items.length };
}

function subscribe(onChange: () => void) {
  listeners.add(onChange);
  return () => listeners.delete(onChange);
}

/** The neighbours of `exceptionId` in the remembered queue (`null` when it was not opened from a list). */
export function useQueueNeighbours(storeId: string, exceptionId: string): Neighbours | null {
  const raw = useSyncExternalStore(subscribe, readRaw, () => null);
  return neighbours(parseQueue(raw, storeId), exceptionId);
}
