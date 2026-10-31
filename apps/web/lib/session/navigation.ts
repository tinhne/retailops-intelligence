/**
 * Returns `next` only when it is a same-origin path, otherwise `/` (SCREEN_SPECIFICATIONS S-01).
 * Rejects absolute URLs, protocol-relative `//host` and backslash tricks that browsers normalise.
 */
export function safeNextPath(next: string | null | undefined): string {
  if (!next || !next.startsWith("/")) return "/";
  if (next.startsWith("//") || next.includes("\\")) return "/";
  if (/[\u0000-\u001f]/.test(next)) return "/";
  try {
    const url = new URL(next, "http://same-origin.invalid");
    if (url.origin !== "http://same-origin.invalid") return "/";
    return `${url.pathname}${url.search}${url.hash}`;
  } catch {
    return "/";
  }
}

export type LoginReason = "expired" | "signed_out";

export function loginPath(options: { next?: string; reason?: LoginReason } = {}): string {
  const params = new URLSearchParams();
  if (options.next && options.next !== "/") params.set("next", options.next);
  if (options.reason) params.set("reason", options.reason);
  const query = params.toString();
  return query ? `/login?${query}` : "/login";
}

export const LAST_STORE_KEY = "ro.lastStoreId";

export function readLastStoreId(): string | null {
  try {
    return window.localStorage.getItem(LAST_STORE_KEY);
  } catch {
    return null;
  }
}

export function writeLastStoreId(storeId: string): void {
  try {
    window.localStorage.setItem(LAST_STORE_KEY, storeId);
  } catch {
    // Storage can be unavailable (private mode). The last store is a convenience only.
  }
}
