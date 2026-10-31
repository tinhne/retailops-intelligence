import { describe, expect, it } from "vitest";

import { errorResponse, jsonResponse, mockFetch } from "@/test/fetch";

import { apiFetch, buildQuery, CSRF_HEADER } from "./client";
import { ApiError, userMessage } from "./errors";

describe("buildQuery", () => {
  it("repeats multi-value filters and drops empty values (API_CONVENTIONS §5)", () => {
    expect(
      buildQuery({ status: ["OPEN", "REOPENED"], q: "", page: 2, assignee_id: undefined, active: true }),
    ).toBe("?status=OPEN&status=REOPENED&page=2&active=true");
  });

  it("returns an empty string when nothing remains", () => {
    expect(buildQuery({ q: null })).toBe("");
    expect(buildQuery()).toBe("");
  });
});

describe("apiFetch", () => {
  it("calls the same-origin API prefix and returns the JSON body", async () => {
    const fetchMock = mockFetch(jsonResponse({ ok: true }));
    await expect(apiFetch("/auth/me", { query: { page: 1 } })).resolves.toEqual({ ok: true });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/auth/me?page=1");
    expect(init?.credentials).toBe("same-origin");
  });

  it("sends the CSRF double-submit header on mutating requests only (ADR-0004)", async () => {
    document.cookie = "ro_csrf=token-123; path=/";
    const fetchMock = mockFetch(jsonResponse({}), jsonResponse({}));

    await apiFetch("/stores/s/exceptions", {});
    await apiFetch("/auth/logout", { method: "POST" });

    const getHeaders = fetchMock.mock.calls[0][1]?.headers as Record<string, string>;
    const postHeaders = fetchMock.mock.calls[1][1]?.headers as Record<string, string>;
    expect(getHeaders[CSRF_HEADER]).toBeUndefined();
    expect(postHeaders[CSRF_HEADER]).toBe("token-123");
  });

  it("serialises plain bodies as JSON", async () => {
    const fetchMock = mockFetch(jsonResponse({}));
    await apiFetch("/auth/login", { method: "POST", body: { email: "a@b.c", password: "x" } });
    const init = fetchMock.mock.calls[0][1];
    expect(init?.body).toBe(JSON.stringify({ email: "a@b.c", password: "x" }));
    expect((init?.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
  });

  it("returns undefined for 204 No Content", async () => {
    mockFetch(new Response(null, { status: 204 }));
    await expect(apiFetch("/auth/logout", { method: "POST" })).resolves.toBeUndefined();
  });

  it("maps the error envelope to ApiError with request ID and Retry-After", async () => {
    mockFetch(
      errorResponse(429, "RATE_LIMITED", "Too many requests.", {
        requestId: "req-42",
        headers: { "retry-after": "34" },
      }),
    );
    const error = await apiFetch("/auth/login", { method: "POST" }).catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 429,
      code: "RATE_LIMITED",
      message: "Too many requests.",
      requestId: "req-42",
      retryAfterSeconds: 34,
    });
  });

  it("derives field names from validation error locations", async () => {
    mockFetch(
      errorResponse(422, "VALIDATION_FAILED", "Request validation failed.", {
        details: [{ loc: ["body", "email"], message: "Invalid email", type: "value_error" }],
      }),
    );
    const error = (await apiFetch("/auth/login", { method: "POST" }).catch((caught: unknown) => caught)) as ApiError;
    expect(error.details[0]).toMatchObject({ field: "email", message: "Invalid email" });
  });

  it("keeps a generic message when a gateway answers with HTML", async () => {
    mockFetch(new Response("<html>Bad gateway</html>", { status: 502, headers: { "x-request-id": "gw-1" } }));
    const error = (await apiFetch("/auth/me").catch((caught: unknown) => caught)) as ApiError;
    expect(error.code).toBe("HTTP_502");
    expect(error.requestId).toBe("gw-1");
    expect(userMessage(error)).toBe("The service is temporarily unavailable.");
  });

  it("reports a network failure as status 0", async () => {
    mockFetch(new TypeError("Failed to fetch"));
    const error = (await apiFetch("/auth/me").catch((caught: unknown) => caught)) as ApiError;
    expect(error.status).toBe(0);
    expect(error.isNetworkError).toBe(true);
  });
});

describe("userMessage", () => {
  it("shows API messages for 4xx and hides details of 5xx", () => {
    expect(userMessage(new ApiError({ status: 403, code: "PERMISSION_DENIED", message: "Your role does not allow this action." }))).toBe(
      "Your role does not allow this action.",
    );
    expect(userMessage(new ApiError({ status: 500, code: "INTERNAL_ERROR", message: "Traceback…" }))).toBe(
      "Something went wrong on our side.",
    );
  });
});
