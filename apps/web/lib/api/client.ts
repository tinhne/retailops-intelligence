import { ApiError, errorFromResponse } from "./errors";

/** Same-origin prefix. Next.js rewrites `/api/*` to FastAPI, so cookies stay first-party (ADR-0004). */
export const API_BASE = "/api/v1";

export const CSRF_COOKIE = "ro_csrf";
export const CSRF_HEADER = "X-CSRF-Token";

type QueryValue = string | number | boolean | null | undefined;
export type QueryParams = Record<string, QueryValue | QueryValue[]>;

export type RequestOptions = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  /** Plain objects are sent as JSON. `FormData` is sent as multipart. */
  body?: unknown;
  query?: QueryParams;
  headers?: Record<string, string>;
  signal?: AbortSignal;
};

const MUTATING = new Set(["POST", "PUT", "PATCH", "DELETE"]);

/** Reads a cookie set by the API. Only the CSRF cookie is readable; the session cookie is HttpOnly. */
export function readCookie(name: string): string | undefined {
  if (typeof document === "undefined") return undefined;
  for (const part of document.cookie.split(";")) {
    const [key, ...rest] = part.trim().split("=");
    if (key === name) return decodeURIComponent(rest.join("="));
  }
  return undefined;
}

/** Multi-value filters repeat the parameter (API_CONVENTIONS §5). Empty values are dropped. */
export function buildQuery(query?: QueryParams): string {
  if (!query) return "";
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    const values = Array.isArray(value) ? value : [value];
    for (const item of values) {
      if (item === undefined || item === null || item === "") continue;
      params.append(key, String(item));
    }
  }
  const text = params.toString();
  return text ? `?${text}` : "";
}

/**
 * Calls the API and returns the parsed JSON body (`undefined` for 204).
 * Mutating requests carry the CSRF double-submit header. Failures throw `ApiError`.
 */
export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json", ...options.headers };
  let body: BodyInit | undefined;

  if (options.body instanceof FormData) {
    body = options.body;
  } else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }

  if (MUTATING.has(method)) {
    const csrf = readCookie(CSRF_COOKIE);
    if (csrf) headers[CSRF_HEADER] = csrf;
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}${buildQuery(options.query)}`, {
      method,
      headers,
      body,
      credentials: "same-origin",
      signal: options.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError({
      status: 0,
      code: "NETWORK_ERROR",
      message: "We couldn't reach the server. Check your connection and try again.",
    });
  }

  if (!response.ok) throw await errorFromResponse(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
