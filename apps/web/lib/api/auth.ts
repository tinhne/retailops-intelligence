import type { Schema } from "@retailops/contracts";

import { apiFetch, CSRF_HEADER } from "./client";

export type MeResponse = Schema<"MeResponse">;
export type Membership = Schema<"MembershipOut">;
export type StoreSummary = Schema<"StoreSummary">;
export type LoginRequest = Schema<"LoginRequest">;
export type Permission = Schema<"Permission">;
export type Role = Schema<"Role">;
type CsrfToken = Schema<"CsrfTokenOut">;
export type AuthOptions = Schema<"AuthOptionsOut">;

/**
 * Sign-in runs before a session exists, so it uses a pre-session CSRF token: `GET /auth/csrf`
 * sets the `ro_csrf` cookie and returns the same value for the header (ADR-0004). A fresh token
 * is fetched for every attempt, so an expired or replaced cookie never blocks sign-in.
 */
async function signInHeaders(): Promise<Record<string, string>> {
  const { csrf_token } = await apiFetch<CsrfToken>("/auth/csrf");
  return { [CSRF_HEADER]: csrf_token };
}

export const authApi = {
  me: (signal?: AbortSignal) => apiFetch<MeResponse>("/auth/me", { signal }),
  options: (signal?: AbortSignal) => apiFetch<AuthOptions>("/auth/options", { signal }),
  login: async (body: LoginRequest) =>
    apiFetch<MeResponse>("/auth/login", { method: "POST", body, headers: await signInHeaders() }),
  demo: async () => apiFetch<MeResponse>("/auth/demo", { method: "POST", headers: await signInHeaders() }),
  logout: () => apiFetch<void>("/auth/logout", { method: "POST" }),
};
