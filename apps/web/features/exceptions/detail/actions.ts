import type { ExceptionActionName, ExceptionDetail } from "@/lib/api/exceptions-api";
import { DEMO_READ_ONLY_REASON, permissionLabels, type Gate } from "@/lib/permissions";
import type { Permission } from "@/lib/api/auth";
import type { ExceptionStatus } from "@/lib/status-maps";

// Which lifecycle buttons to show and how (S-04 "Actions", COMPONENT_INVENTORY C-56). The API
// decides what is possible: `available_actions` are allowed for this caller, `blocked_actions`
// are possible in this state but refused by permission or ownership. Everything else is not
// possible in the current status and is not shown.

export type BarAction = "acknowledge" | "start" | "claim" | "resolve" | "dismiss" | "reopen";
export type ActionItem = { kind: BarAction; label: string; gate: Gate; opensDialog: boolean };
export type ActionLayout = { primary?: ActionItem; secondary: ActionItem[]; more: ActionItem[] };

export const ACTION_LABELS: Record<BarAction, string> = {
  acknowledge: "Acknowledge",
  start: "Start work",
  claim: "Claim",
  resolve: "Resolve…",
  dismiss: "Dismiss…",
  reopen: "Reopen…",
};

const OPENS_DIALOG: Record<BarAction, boolean> = {
  acknowledge: false,
  start: false,
  claim: false,
  resolve: true,
  dismiss: true,
  reopen: true,
};

/** The permission each command needs (mirrors ACTION_PERMISSION in the API's lifecycle module). */
export const ACTION_PERMISSION: Record<ExceptionActionName, Permission> = {
  acknowledge: "exceptions.work",
  start: "exceptions.work",
  resolve: "exceptions.work",
  claim: "exceptions.work",
  add_note: "exceptions.work",
  dismiss: "exceptions.manage",
  reopen: "exceptions.manage",
  assign: "exceptions.assign",
  set_due_date: "exceptions.assign",
};

/** Placement per status: primary, secondary, then the More menu (S-04 action table). */
const LAYOUT: Record<ExceptionStatus, { primary?: BarAction; secondary: BarAction[]; more: BarAction[] }> = {
  OPEN: { primary: "acknowledge", secondary: ["start", "claim"], more: ["resolve", "dismiss"] },
  ACKNOWLEDGED: { primary: "start", secondary: ["claim", "resolve"], more: ["dismiss"] },
  IN_PROGRESS: { primary: "resolve", secondary: [], more: ["dismiss"] },
  REOPENED: { primary: "start", secondary: ["acknowledge", "claim"], more: ["resolve", "dismiss"] },
  RESOLVED: { primary: "reopen", secondary: [], more: [] },
  DISMISSED: { primary: "reopen", secondary: [], more: [] },
};

/** The disabled reason shown to the person (IA §5 copy, S-04 action table). */
export function blockedReason(
  action: ExceptionActionName,
  code: string,
  apiReason: string,
  context: { isDemo: boolean; assigneeName?: string | null },
): string {
  if (code === "PERMISSION_DENIED") {
    if (context.isDemo) return DEMO_READ_ONLY_REASON;
    if (action === "dismiss") return "Dismissing requires the Manage exceptions permission.";
    if (action === "reopen") return "Reopening requires the Manage exceptions permission.";
    return `You need the ${permissionLabels[ACTION_PERMISSION[action]]} permission. Ask an owner or manager.`;
  }
  if (code === "ASSIGNED_TO_ANOTHER_USER" && action === "start" && context.assigneeName) {
    return `This exception is assigned to ${context.assigneeName}. Ask a manager to reassign it.`;
  }
  return apiReason;
}

/** Gate for any API action: allowed, blocked with a reason, or `undefined` when impossible now. */
export function gateFor(exception: ExceptionDetail, action: ExceptionActionName, isDemo: boolean): Gate | undefined {
  if (exception.available_actions.includes(action)) return { allowed: true };
  const blocked = exception.blocked_actions.find((item) => item.action === action);
  if (!blocked) return undefined;
  return {
    allowed: false,
    reason: blockedReason(action, blocked.code, blocked.reason, { isDemo, assigneeName: exception.assignee?.full_name }),
  };
}

export function getExceptionActions(exception: ExceptionDetail, isDemo: boolean): ActionLayout {
  const plan = LAYOUT[exception.status];
  const item = (kind: BarAction): ActionItem | undefined => {
    // Claim only makes sense on an unassigned exception (hidden when assigned).
    if (kind === "claim" && exception.assignee) return undefined;
    const gate = gateFor(exception, kind, isDemo);
    return gate ? { kind, label: ACTION_LABELS[kind], gate, opensDialog: OPENS_DIALOG[kind] } : undefined;
  };
  const present = (kinds: BarAction[]) => kinds.map(item).filter((value): value is ActionItem => Boolean(value));
  return {
    primary: plan.primary ? item(plan.primary) : undefined,
    secondary: present(plan.secondary),
    more: present(plan.more),
  };
}
