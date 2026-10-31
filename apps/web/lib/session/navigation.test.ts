import { describe, expect, it } from "vitest";

import { loginPath, safeNextPath } from "./navigation";

describe("safeNextPath (S-01: same-origin paths only)", () => {
  it.each([
    ["/s/abc/overview", "/s/abc/overview"],
    ["/s/abc/exceptions?view=mine#evidence", "/s/abc/exceptions?view=mine#evidence"],
    ["/", "/"],
  ])("keeps %s", (input, expected) => {
    expect(safeNextPath(input)).toBe(expected);
  });

  it.each([
    [null],
    [""],
    ["https://evil.example/phish"],
    ["//evil.example/phish"],
    ["/\\evil.example"],
    ["javascript:alert(1)"],
    ["relative/path"],
    ["/\u0000/x"],
  ])("rejects %j", (input) => {
    expect(safeNextPath(input)).toBe("/");
  });
});

describe("loginPath", () => {
  it("adds next and reason when present", () => {
    expect(loginPath({ next: "/s/a/overview", reason: "expired" })).toBe(
      "/login?next=%2Fs%2Fa%2Foverview&reason=expired",
    );
    expect(loginPath({ reason: "signed_out" })).toBe("/login?reason=signed_out");
    expect(loginPath({ next: "/" })).toBe("/login");
  });
});
