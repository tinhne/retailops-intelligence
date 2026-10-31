import type { Permission, Role } from "@/lib/api/auth";

/** UI labels for the code-defined permission matrix (ADR-0007, IA §5). */
export const permissionLabels: Record<Permission, string> = {
  "dashboard.read": "View the overview",
  "catalog.read": "View products",
  "orders.read": "View orders",
  "inventory.read": "View inventory",
  "exceptions.read": "View exceptions",
  "exceptions.work": "Work on exceptions",
  "exceptions.assign": "Assign exceptions",
  "exceptions.manage": "Manage exceptions",
  "evaluations.run": "Run analysis",
  "imports.read": "View imports",
  "imports.run": "Run imports",
  "analytics.read": "View analytics",
  "copilot.use": "Use the copilot",
  "audit.read": "View the audit log",
  "settings.read": "View settings",
  "settings.manage": "Manage settings",
  "users.read": "View users",
  "users.manage": "Manage users",
};

export const roleLabels: Record<Role, string> = {
  OWNER: "Owner",
  MANAGER: "Manager",
  STAFF: "Staff",
  ANALYST: "Analyst",
  VIEWER: "Viewer",
};

/** Whether an action is allowed, and if not, the reason shown to the person (COMPONENT_INVENTORY §2). */
export type Gate = { allowed: true } | { allowed: false; reason: string };

export const DEMO_READ_ONLY_REASON = "The public demo is read-only.";

/**
 * Decides an action gate from the caller's permissions (IA §5 disabled-reason copy). The backend
 * enforces the same rules; this only keeps the UI honest about what will be refused.
 */
export function gateFor(
  required: Permission | Permission[],
  context: { permissions: ReadonlySet<Permission>; isDemo: boolean },
): Gate {
  const missing = (Array.isArray(required) ? required : [required]).filter(
    (permission) => !context.permissions.has(permission),
  );
  if (missing.length === 0) return { allowed: true };
  if (context.isDemo) return { allowed: false, reason: DEMO_READ_ONLY_REASON };
  return {
    allowed: false,
    reason: `You need the ${permissionLabels[missing[0]]} permission. Ask an owner or manager.`,
  };
}
