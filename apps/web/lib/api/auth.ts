import type { Schema } from "@retailops/contracts";

import { apiFetch } from "./client";

export type MeResponse = Schema<"MeResponse">;
export type Membership = Schema<"MembershipOut">;
export type StoreSummary = Schema<"StoreSummary">;
export type LoginRequest = Schema<"LoginRequest">;
export type Permission = Schema<"Permission">;
export type Role = Schema<"Role">;

export const authApi = {
  me: (signal?: AbortSignal) => apiFetch<MeResponse>("/auth/me", { signal }),
  login: (body: LoginRequest) => apiFetch<MeResponse>("/auth/login", { method: "POST", body }),
  demo: () => apiFetch<MeResponse>("/auth/demo", { method: "POST" }),
  logout: () => apiFetch<void>("/auth/logout", { method: "POST" }),
};
