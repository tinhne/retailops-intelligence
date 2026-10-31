"use client";

import { useCallback, useSyncExternalStore } from "react";

/** Subscribes to a CSS media query. `serverValue` is used before hydration. */
export function useMediaQuery(query: string, serverValue = true): boolean {
  const subscribe = useCallback(
    (onChange: () => void) => {
      const list = window.matchMedia(query);
      list.addEventListener("change", onChange);
      return () => list.removeEventListener("change", onChange);
    },
    [query],
  );
  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(query).matches,
    () => serverValue,
  );
}

function subscribeOnline(onChange: () => void) {
  window.addEventListener("online", onChange);
  window.addEventListener("offline", onChange);
  return () => {
    window.removeEventListener("online", onChange);
    window.removeEventListener("offline", onChange);
  };
}

/** `navigator.onLine`, kept current (SCREEN_SPECIFICATIONS §0.2 "Offline"). */
export function useOnline(): boolean {
  return useSyncExternalStore(
    subscribeOnline,
    () => navigator.onLine,
    () => true,
  );
}

const storageListeners = new Set<() => void>();

/** A boolean persisted in localStorage, shared by every component that reads the same key. */
export function useStoredBoolean(key: string, fallback: boolean): [boolean, (value: boolean) => void] {
  const subscribe = useCallback((onChange: () => void) => {
    storageListeners.add(onChange);
    window.addEventListener("storage", onChange);
    return () => {
      storageListeners.delete(onChange);
      window.removeEventListener("storage", onChange);
    };
  }, []);

  const read = () => {
    try {
      const raw = window.localStorage.getItem(key);
      return raw === null ? fallback : raw === "true";
    } catch {
      return fallback;
    }
  };

  const value = useSyncExternalStore(subscribe, read, () => fallback);

  const setValue = useCallback(
    (next: boolean) => {
      try {
        window.localStorage.setItem(key, String(next));
      } catch {
        // Storage can be unavailable (private mode). The preference then lasts for the page only.
      }
      storageListeners.forEach((listener) => listener());
    },
    [key],
  );

  return [value, setValue];
}
