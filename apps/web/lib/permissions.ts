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

/** One line per permission for the role matrix (ROLE_AND_PERMISSION_WORKFLOW §3, S-17). */
export const permissionDescriptions: Record<Permission, string> = {
  "dashboard.read": "Overview dashboard and attention list.",
  "catalog.read": "Products and suppliers.",
  "orders.read": "Orders, order lines and order history.",
  "inventory.read": "Stock positions, health, the movement ledger and reservations.",
  "exceptions.read": "Exception inbox and detail: evidence, history and notes.",
  "exceptions.work": "Acknowledge, claim, start and resolve own exceptions, and add notes.",
  "exceptions.assign": "Assign, reassign or unassign exceptions and change due dates.",
  "exceptions.manage": "Dismiss, reopen and resolve any exception.",
  "evaluations.run": "Start a manual analysis run.",
  "imports.read": "Import history, row issues, the issues CSV and templates.",
  "imports.run": "Upload, validate, apply, discard and retry imports.",
  "analytics.read": "Trends and performance views.",
  "copilot.use": "Ask the copilot and run AI investigations.",
  "audit.read": "The audit log.",
  "settings.read": "Store settings.",
  "settings.manage": "Change thresholds and priority weights.",
  "users.read": "Members of the organization and their roles.",
  "users.manage": "Add members, change roles, deactivate and reactivate.",
};

export const roleLabels: Record<Role, string> = {
  OWNER: "Owner",
  MANAGER: "Manager",
  STAFF: "Staff",
  ANALYST: "Analyst",
  VIEWER: "Viewer",
};

/** One line per role for the role pickers (S-17 Change role dialog). */
export const roleDescriptions: Record<Role, string> = {
  OWNER: "Full access, including users.",
  MANAGER: "Runs operations. Everything except managing users.",
  STAFF: "Works on exceptions. Reads operational data.",
  ANALYST: "Read-only, plus copilot and audit log.",
  VIEWER: "Read-only demo access.",
};

/** Roles in the order the matrix and pickers show them. */
export const ROLES: Role[] = ["OWNER", "MANAGER", "STAFF", "ANALYST", "VIEWER"];

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
