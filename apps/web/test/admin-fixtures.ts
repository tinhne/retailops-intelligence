import { vi } from "vitest";

import type { AuditEntry, OrganizationMember, RolePermissions, StoreSettings } from "@/lib/api/admin-api";
import type { Permission } from "@/lib/api/auth";

// Shapes as the API returns them (OrganizationMemberOut, RolePermissionsOut, StoreSettingsOut,
// AuditLogOut). Names are fictional, like the demo organization's.

type Handler = (init: RequestInit | undefined) => Response;

/**
 * Answers `fetch` by method and path suffix ("PATCH /members/m-staff"), for screens that read and
 * write the same resource. Unmatched requests fail the test.
 */
export function methodFetch(handlers: Record<string, Handler>) {
  const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    const path = url.split("?")[0];
    const method = init?.method ?? "GET";
    const key = Object.keys(handlers).find((candidate) => {
      const [verb, suffix] = candidate.split(" ");
      return verb === method && path.endsWith(suffix);
    });
    if (!key) throw new Error(`Unexpected request in test: ${method} ${url}`);
    return handlers[key](init);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

/** The JSON body of the first call to a path suffix with a method. */
export function sentBody(fetchMock: ReturnType<typeof methodFetch>, method: string, suffix: string): unknown {
  const call = fetchMock.mock.calls.find(([input, init]) => (init?.method ?? "GET") === method && String(input).split("?")[0].endsWith(suffix));
  return call ? JSON.parse(String(call[1]?.body)) : undefined;
}

export function memberFixture(overrides: Partial<OrganizationMember> = {}): OrganizationMember {
  return {
    id: "m-staff",
    user_id: "u-staff",
    full_name: "Sam Ortiz",
    email: "staff@kestrel.example",
    role: "STAFF",
    status: "ACTIVE",
    joined_at: "2026-09-01T12:00:00Z",
    last_login_at: "2026-10-31T13:00:00Z",
    ...overrides,
  };
}

/** The current user of `testStore()` (user-1) as the organization's only owner. */
export const ownerMember = (overrides: Partial<OrganizationMember> = {}) =>
  memberFixture({ id: "m-owner", user_id: "user-1", full_name: "Priya Raman", email: "owner@kestrel.example", role: "OWNER", ...overrides });

const READ: Permission[] = [
  "dashboard.read",
  "catalog.read",
  "orders.read",
  "inventory.read",
  "exceptions.read",
  "imports.read",
  "analytics.read",
  "copilot.use",
  "settings.read",
];
const ALL: Permission[] = [
  ...READ,
  "exceptions.work",
  "exceptions.assign",
  "exceptions.manage",
  "evaluations.run",
  "imports.run",
  "audit.read",
  "settings.manage",
  "users.read",
  "users.manage",
];

/** The matrix `GET /roles` returns (ADR-0007), used as test input only. */
export function rolesFixture(): RolePermissions[] {
  return [
    { role: "OWNER", permissions: ALL },
    { role: "MANAGER", permissions: ALL.filter((permission) => permission !== "users.manage") },
    { role: "STAFF", permissions: [...READ, "exceptions.work"] },
    { role: "ANALYST", permissions: [...READ, "audit.read"] },
    { role: "VIEWER", permissions: [...READ, "audit.read"] },
  ];
}

export function settingsFixture(overrides: Partial<StoreSettings> = {}): StoreSettings {
  return {
    fulfillment_sla_hours: 48,
    stall_threshold_hours: 12,
    refund_overdue_hours: 24,
    approaching_reorder_factor: "1.25",
    velocity_window_days: 28,
    reopen_window_hours: 72,
    exposure_cap: "5000.00",
    priority_weights: {
      severity: { CRITICAL: 50, HIGH: 35, MEDIUM: 20, LOW: 8 },
      affected_orders_per_order: 3,
      affected_orders_cap: 15,
      exposure_cap_points: 15,
      deadline: { overdue: 12, within_24h: 8, within_72h: 4 },
      age_points_per_day: 2,
      age_cap: 8,
    },
    evaluation_interval_minutes: 15,
    updated_at: "2026-10-30T10:00:00Z",
    ...overrides,
  };
}

export function auditEntryFixture(overrides: Partial<AuditEntry> = {}): AuditEntry {
  return {
    id: "a1",
    occurred_at: "2026-10-31T14:05:00Z",
    action: "exception.resolve",
    actor_user_id: "u-staff",
    actor_name: "Sam Ortiz",
    store_id: "f0da0f22-b9e0-4483-b144-e9f0f8703d13",
    target_type: "exception",
    target_id: "e1",
    details: { reference: "EXC-1042", from_status: "IN_PROGRESS", resolution_code: "FIXED_AT_SOURCE" },
    request_id: "req-1",
    ...overrides,
  };
}
