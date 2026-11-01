import type { AuditEntry } from "@/lib/api/admin-api";

// Labels for the audit actions the API records today (S-15). Unknown actions fall back to the raw
// code, so a new action never breaks the page.

export const AUDIT_ACTION_GROUPS = [
  { prefix: "auth.", label: "Sign-in and sessions" },
  { prefix: "user.", label: "Users" },
  { prefix: "settings.", label: "Settings" },
  { prefix: "exception.", label: "Exceptions" },
  { prefix: "import.", label: "Imports" },
  { prefix: "evaluation.", label: "Analysis runs" },
] as const;

export const AUDIT_ACTION_PREFIXES = AUDIT_ACTION_GROUPS.map((group) => group.prefix);

export const auditActionLabels: Record<string, string> = {
  "auth.login": "Signed in",
  "auth.demo_login": "Started a demo session",
  "auth.logout": "Signed out",
  "auth.login_failed": "Sign-in failed",
  "auth.session_revoked": "Sessions ended",
  "user.create": "Added member",
  "user.role_change": "Changed role",
  "user.deactivate": "Deactivated member",
  "user.reactivate": "Reactivated member",
  "settings.update": "Updated settings",
  "exception.acknowledge": "Acknowledged exception",
  "exception.start": "Started work on exception",
  "exception.resolve": "Resolved exception",
  "exception.dismiss": "Dismissed exception",
  "exception.reopen": "Reopened exception",
  "exception.assign": "Assigned exception",
  "exception.note": "Added note",
  "exception.due_date": "Changed due date",
  "import.applied": "Applied import",
  "import.failed": "Import failed",
  "import.discarded": "Discarded import",
  "evaluation.run": "Ran analysis",
};

/** The label for an entry, refined by its details where one action covers several cases. */
export function auditActionLabel(entry: Pick<AuditEntry, "action" | "details">): string {
  if (entry.action === "exception.assign") {
    if (entry.details.claimed === true) return "Claimed exception";
    if (entry.details.to_assignee_id === null) return "Unassigned exception";
  }
  return auditActionLabels[entry.action] ?? entry.action;
}
