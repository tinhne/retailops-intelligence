import { describe, expect, it } from "vitest";

import {
  exactReference,
  isFiltered,
  parseInboxParams,
  serializeInboxParams,
  toApiQuery,
  updateParams,
} from "./inbox-params";

const NOW = new Date("2026-11-01T12:00:00Z");
const parse = (query: string, view?: "active" | "mine") => parseInboxParams(new URLSearchParams(query), view);

describe("inbox URL state (S-03, IA §9)", () => {
  it("defaults to the given view with its default sort", () => {
    expect(parse("").params).toMatchObject({ view: "active", sort: "-priority_score", page: 1, page_size: 25 });
    expect(parse("", "mine").params.view).toBe("mine");
    expect(parse("view=closed").params.sort).toBe("-first_detected_at");
  });

  it("drops unknown values and reports them", () => {
    const { params, invalid } = parse("severity=CRITICAL&severity=LOUD&sort=title&page=-2&page_size=7&assignee=bob");
    expect(params.severity).toEqual(["CRITICAL"]);
    expect(params.sort).toBe("-priority_score");
    expect(params.page).toBe(1);
    expect(params.page_size).toBe(25);
    expect(params.assignee).toBeNull();
    expect(invalid.sort()).toEqual(["assignee", "page", "page_size", "severity", "sort"]);
  });

  it("only accepts statuses inside the current view", () => {
    expect(parse("view=triage&status=OPEN&status=RESOLVED").params.status).toEqual(["OPEN"]);
    expect(parse("view=closed&status=DISMISSED").params.status).toEqual(["DISMISSED"]);
  });

  it("round-trips through the URL without default noise", () => {
    const { params } = parse("view=active&severity=HIGH&severity=CRITICAL&q=oversold&page=2");
    expect(serializeInboxParams(params).toString()).toBe("view=active&q=oversold&severity=HIGH&severity=CRITICAL&page=2");
  });
});

describe("API query", () => {
  it("applies view presets", () => {
    expect(toApiQuery(parse("view=triage").params, NOW).status).toEqual(["OPEN", "REOPENED"]);
    expect(toApiQuery(parse("view=mine").params, NOW).assignee).toBe("me");
    expect(toApiQuery(parse("view=unassigned&assignee=me").params, NOW).assignee).toBe("unassigned");
    expect(toApiQuery(parse("view=closed").params, NOW).status).toEqual(["RESOLVED", "DISMISSED"]);
  });

  it("narrows statuses within the view and computes due_to when the request is made", () => {
    expect(toApiQuery(parse("view=active&status=REOPENED").params, NOW).status).toEqual(["REOPENED"]);
    expect(toApiQuery(parse("due=overdue").params, NOW).due_to).toBe("2026-11-01T12:00:00.000Z");
    expect(toApiQuery(parse("due=24h").params, NOW).due_to).toBe("2026-11-02T12:00:00.000Z");
    expect(toApiQuery(parse("q=%20%20").params, NOW).q).toBeUndefined();
  });
});

describe("updates", () => {
  it("resets the page on any filter change but not on paging", () => {
    const { params } = parse("page=3");
    expect(updateParams(params, { severity: ["LOW"] }).page).toBe(1);
    expect(updateParams(params, { page: 4 }).page).toBe(4);
  });

  it("clears view-specific state when switching views", () => {
    const { params } = parse("view=active&status=IN_PROGRESS&assignee=me&sort=due_at");
    expect(updateParams(params, { view: "closed" })).toMatchObject({ status: [], sort: "-first_detected_at" });
    expect(updateParams(params, { view: "mine" }).assignee).toBeNull();
  });

  it("knows when a view is filtered", () => {
    expect(isFiltered(parse("view=triage").params)).toBe(false);
    expect(isFiltered(parse("view=triage&q=x").params)).toBe(true);
  });

  it("recognises exact references", () => {
    expect(exactReference("exc-1042")).toBe("EXC-1042");
    expect(exactReference(" 1042 ")).toBe("EXC-1042");
    expect(exactReference("oversold")).toBeNull();
  });
});
