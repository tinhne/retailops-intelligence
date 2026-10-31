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
