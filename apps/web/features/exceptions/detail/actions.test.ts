import { describe, expect, it } from "vitest";

import type { ExceptionActionName, ExceptionDetail } from "@/lib/api/exceptions-api";
import type { ExceptionStatus } from "@/lib/status-maps";

import { getExceptionActions } from "./actions";

type Blocked = { action: ExceptionActionName; code: string; reason: string };

function detail(status: ExceptionStatus, available: ExceptionActionName[], blocked: Blocked[] = [], assignee: string | null = null) {
  return {
    status,
    available_actions: available,
    blocked_actions: blocked,
    assignee: assignee ? { id: "u2", full_name: assignee } : null,
  } as unknown as ExceptionDetail;
}

const kinds = (layout: ReturnType<typeof getExceptionActions>) => ({
  primary: layout.primary?.kind,
  secondary: layout.secondary.map((item) => item.kind),
  more: layout.more.map((item) => item.kind),
});

describe("getExceptionActions (S-04 action table, STATE_MACHINES §3.2)", () => {
  it("lays out an open, unassigned exception for someone who can do everything", () => {
    const layout = getExceptionActions(
      detail("OPEN", ["acknowledge", "start", "claim", "resolve", "dismiss", "assign", "add_note", "set_due_date"]),
      false,
    );
    expect(kinds(layout)).toEqual({ primary: "acknowledge", secondary: ["start", "claim"], more: ["resolve", "dismiss"] });
    expect(layout.more[0]).toMatchObject({ label: "Resolve…", opensDialog: true, gate: { allowed: true } });
  });

  it("hides Claim once someone is assigned", () => {
    const layout = getExceptionActions(detail("ACKNOWLEDGED", ["start", "resolve"], [], "Marcus Lee"), false);
    expect(kinds(layout)).toEqual({ primary: "start", secondary: ["resolve"], more: [] });
  });

  it("offers Resolve as the primary action while in progress, and Reopen once closed", () => {
    expect(kinds(getExceptionActions(detail("IN_PROGRESS", ["resolve", "dismiss"]), false)).primary).toBe("resolve");
    expect(kinds(getExceptionActions(detail("RESOLVED", ["reopen"]), false))).toEqual({ primary: "reopen", secondary: [], more: [] });
  });

  it("omits actions the state rules out entirely", () => {
    // A superseded exception cannot be reopened by anyone: the API lists it nowhere.
    expect(getExceptionActions(detail("RESOLVED", []), false).primary).toBeUndefined();
  });

  it("keeps blocked actions visible with the read-only reason in the demo", () => {
    const denied = (action: ExceptionActionName): Blocked => ({ action, code: "PERMISSION_DENIED", reason: "Your role does not allow this action." });
    const layout = getExceptionActions(detail("OPEN", [], ["acknowledge", "start", "claim", "resolve", "dismiss"].map((a) => denied(a as ExceptionActionName))), true);
    expect(layout.primary?.gate).toEqual({ allowed: false, reason: "The public demo is read-only." });
    expect(layout.more.map((item) => item.gate)).toEqual([
      { allowed: false, reason: "The public demo is read-only." },
      { allowed: false, reason: "The public demo is read-only." },
    ]);
  });

  it("explains permission and ownership refusals outside the demo", () => {
    const layout = getExceptionActions(
      detail(
        "IN_PROGRESS",
        [],
        [
          { action: "resolve", code: "NOT_ASSIGNEE", reason: "Only the assignee or a manager can resolve this exception." },
          { action: "dismiss", code: "PERMISSION_DENIED", reason: "Your role does not allow this action." },
        ],
        "Sofia Alvarez",
      ),
      false,
    );
    expect(layout.primary?.gate).toEqual({ allowed: false, reason: "Only the assignee or a manager can resolve this exception." });
    expect(layout.more[0].gate).toEqual({ allowed: false, reason: "Dismissing requires the Manage exceptions permission." });
  });

  it("names the assignee when someone else's work cannot be started", () => {
    const layout = getExceptionActions(
      detail("ACKNOWLEDGED", [], [{ action: "start", code: "ASSIGNED_TO_ANOTHER_USER", reason: "This exception is assigned to another user." }], "Sofia Alvarez"),
      false,
    );
    expect(layout.primary?.gate).toEqual({ allowed: false, reason: "This exception is assigned to Sofia Alvarez. Ask a manager to reassign it." });
  });
});
