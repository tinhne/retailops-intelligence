"use client";

import { useSyncExternalStore } from "react";

// One shared 60 s ticker for every relative time on screen (COMPONENT_INVENTORY C-05), rather
// than an interval per component.
const listeners = new Set<() => void>();
let now = Date.now();
let timer: number | undefined;

function subscribe(listener: () => void) {
  listeners.add(listener);
  if (timer === undefined) {
    now = Date.now();
    timer = window.setInterval(() => {
      now = Date.now();
      listeners.forEach((notify) => notify());
    }, 60_000);
  }
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0 && timer !== undefined) {
      window.clearInterval(timer);
      timer = undefined;
    }
  };
}

/** The current time, refreshed every minute. */
export function useNow(): Date {
  const value = useSyncExternalStore(
    subscribe,
    () => now,
    () => now,
  );
  return new Date(value);
}
