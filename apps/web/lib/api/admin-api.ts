import type { Schema } from "@retailops/contracts";

import { apiFetch, type QueryParams } from "./client";

export type OrganizationMember = Schema<"OrganizationMemberOut">;
export type MemberStatus = Schema<"MemberStatus">;
export type MemberCreate = Schema<"MemberCreate">;
export type MemberCreated = Schema<"MemberCreated">;
export type MemberUpdate = Schema<"MemberUpdate">;
export type RolePermissions = Schema<"RolePermissionsOut">;
export type StoreSettings = Schema<"StoreSettingsOut">;
export type StoreSettingsUpdate = Schema<"StoreSettingsUpdate">;
export type PriorityWeights = Schema<"PriorityWeights">;
export type AuditEntry = Schema<"AuditLogOut">;

const members = (organizationId: string) => `/organizations/${organizationId}/members`;

/** Administration (S-15 audit log, S-16 settings, S-17 users and roles). */
export const adminApi = {
  members: (organizationId: string, signal?: AbortSignal) =>
    apiFetch<Schema<"OrganizationMemberList">>(members(organizationId), { signal }),
  addMember: (organizationId: string, body: MemberCreate) =>
    apiFetch<MemberCreated>(members(organizationId), { method: "POST", body }),
  updateMember: (organizationId: string, membershipId: string, body: MemberUpdate) =>
    apiFetch<OrganizationMember>(`${members(organizationId)}/${membershipId}`, { method: "PATCH", body }),
  /** The code-defined role → permission matrix (ADR-0007). */
  roles: (signal?: AbortSignal) => apiFetch<RolePermissions[]>("/roles", { signal }),

  settings: (storeId: string, signal?: AbortSignal) => apiFetch<StoreSettings>(`/stores/${storeId}/settings`, { signal }),
  /** Partial update: only the changed fields are sent. */
  updateSettings: (storeId: string, body: StoreSettingsUpdate) =>
    apiFetch<StoreSettings>(`/stores/${storeId}/settings`, { method: "PATCH", body }),

  auditLogs: (storeId: string, query: QueryParams, signal?: AbortSignal) =>
    apiFetch<Schema<"Page_AuditLogOut_">>(`/stores/${storeId}/audit-logs`, { query, signal }),
};

export const adminKeys = {
  /** Members belong to the organization, so every store of it shares this cache entry. */
  members: (organizationId: string) => ["organization", organizationId, "members"] as const,
  roles: () => ["roles"] as const,
  settings: (storeId: string) => ["store", storeId, "settings"] as const,
  auditLogs: (storeId: string, query: QueryParams) => ["store", storeId, "audit-logs", query] as const,
};
