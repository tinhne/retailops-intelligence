import { describe, expect, it } from "vitest";

import type { Permission } from "@/lib/api/auth";

import { DEMO_READ_ONLY_REASON, gateFor } from "./permissions";

const perms = (...values: Permission[]) => new Set<Permission>(values);

describe("gateFor (IA §5 disabled-reason copy)", () => {
  it("allows when every permission is held", () => {
    expect(gateFor(["exceptions.read", "exceptions.work"], { permissions: perms("exceptions.read", "exceptions.work"), isDemo: false })).toEqual({
      allowed: true,
    });
  });

  it("explains a missing permission outside the demo", () => {
    expect(gateFor("evaluations.run", { permissions: perms(), isDemo: false })).toEqual({
      allowed: false,
      reason: "You need the Run analysis permission. Ask an owner or manager.",
    });
  });

  it("always gives the read-only reason in a demo organization", () => {
    expect(gateFor("imports.run", { permissions: perms(), isDemo: true })).toEqual({
      allowed: false,
      reason: DEMO_READ_ONLY_REASON,
    });
  });
});
