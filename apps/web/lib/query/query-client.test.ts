import { describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/errors";

import { makeQueryClient, retryDelay, shouldRetry } from "./query-client";

const error = (status: number, code = `HTTP_${status}`) => new ApiError({ status, code, message: "x" });

describe("retry policy (SCREEN_SPECIFICATIONS §0.3)", () => {
  it("retries network and 5xx failures twice", () => {
    expect(shouldRetry(0, error(0, "NETWORK_ERROR"))).toBe(true);
    expect(shouldRetry(1, error(503))).toBe(true);
    expect(shouldRetry(2, error(503))).toBe(false);
  });

  it("never retries 4xx answers", () => {
    for (const status of [400, 401, 403, 404, 409, 422, 429]) {
      expect(shouldRetry(0, error(status))).toBe(false);
    }
  });

  it("waits 1 s, then 3 s", () => {
    expect(retryDelay(0)).toBe(1000);
    expect(retryDelay(1)).toBe(3000);
  });
});

describe("session expiry", () => {
  it("reports a 401 with its code", async () => {
    const onSessionExpired = vi.fn();
    const client = makeQueryClient({ onSessionExpired });
    await client
      .fetchQuery({ queryKey: ["x"], queryFn: () => Promise.reject(error(401, "SESSION_EXPIRED")) })
      .catch(() => undefined);
    expect(onSessionExpired).toHaveBeenCalledWith("SESSION_EXPIRED");
  });

  it("ignores 401s on requests that expect them (the sign-in probe)", async () => {
    const onSessionExpired = vi.fn();
    const client = makeQueryClient({ onSessionExpired });
    await client
      .fetchQuery({
        queryKey: ["probe"],
        queryFn: () => Promise.reject(error(401, "UNAUTHENTICATED")),
        meta: { skipSessionExpiry: true },
      })
      .catch(() => undefined);
    expect(onSessionExpired).not.toHaveBeenCalled();
  });

  it("ignores other errors", async () => {
    const onSessionExpired = vi.fn();
    const client = makeQueryClient({ onSessionExpired });
    await client
      .fetchQuery({ queryKey: ["y"], queryFn: () => Promise.reject(error(403)), retry: false })
      .catch(() => undefined);
    expect(onSessionExpired).not.toHaveBeenCalled();
  });
});
