"use client";

import { useEffect, useState } from "react";

/**
 * Seconds left from `seconds`, counting down once per second. A new `key` restarts the
 * countdown even when the duration is the same (a second 429 with the same Retry-After).
 */
export function useCountdown(seconds: number | undefined, key?: unknown): number {
  const [state, setState] = useState({ key, seconds, left: seconds ?? 0 });

  // Restart during render when the input changes (React's "adjusting state on prop change").
  if (state.key !== key || state.seconds !== seconds) {
    setState({ key, seconds, left: seconds ?? 0 });
  }

  useEffect(() => {
    if (!seconds) return;
    const started = Date.now();
    const timer = window.setInterval(() => {
      const left = Math.max(0, seconds - Math.floor((Date.now() - started) / 1000));
      setState((current) => ({ ...current, left }));
      if (left === 0) window.clearInterval(timer);
    }, 1000);
    return () => window.clearInterval(timer);
  }, [seconds, key]);

  return state.left;
}
