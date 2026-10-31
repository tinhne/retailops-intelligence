import { vi } from "vitest";

/** A JSON `Response` as the API would send it. */
export function jsonResponse(body: unknown, init: { status?: number; headers?: Record<string, string> } = {}) {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status: init.status ?? 200,
    headers: { "content-type": "application/json", ...init.headers },
  });
}

/** The API error envelope (apps/api/app/core/errors.py). */
export function errorResponse(
  status: number,
  code: string,
  message: string,
  extra: { requestId?: string; headers?: Record<string, string>; details?: unknown[] } = {},
) {
  return jsonResponse(
    { error: { code, message, details: extra.details ?? [], request_id: extra.requestId ?? null } },
    { status, headers: extra.headers },
  );
}

export function mockFetch(...responses: Array<Response | Error>) {
  const fetchMock = vi.fn<typeof fetch>();
  for (const response of responses) {
    if (response instanceof Error) fetchMock.mockRejectedValueOnce(response);
    else fetchMock.mockResolvedValueOnce(response);
  }
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

type Route = Response | (() => Response) | Error;

/**
 * Answers `fetch` by URL path, for screens that fire several requests in parallel. The first
 * route whose key is contained in the request path wins. Unmatched requests fail the test.
 */
export function routeFetch(routes: Record<string, Route>) {
  const fetchMock = vi.fn<typeof fetch>(async (input) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    const path = url.split("?")[0];
    const match = Object.keys(routes).find((key) => path.endsWith(key));
    if (!match) throw new Error(`Unexpected request in test: ${url}`);
    const route = routes[match];
    if (route instanceof Error) throw route;
    return typeof route === "function" ? route() : route.clone();
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}
