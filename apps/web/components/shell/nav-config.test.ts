import { Boxes, LayoutDashboard } from "lucide-react";
import { describe, expect, it } from "vitest";

import type { Permission } from "@/lib/api/auth";

import { activeNavItem, NAV_GROUPS, visibleNav, type NavGroup } from "./nav-config";

const groups: NavGroup[] = [
  { items: [{ label: "Overview", segment: "overview", icon: LayoutDashboard, permission: ["dashboard.read"], ready: true }] },
  {
    label: "Commerce",
    items: [
      { label: "Inventory", segment: "inventory", icon: Boxes, permission: ["inventory.read"], ready: true },
      { label: "Movements", segment: "inventory/movements", icon: Boxes, permission: ["inventory.read"], ready: true },
    ],
  },
  {
    label: "Administration",
    items: [{ label: "Users & roles", segment: "admin/users", icon: Boxes, permission: ["users.read"], ready: true }],
  },
  {
    label: "Later",
    items: [{ label: "Not built", segment: "later", icon: Boxes, permission: ["dashboard.read"], ready: false }],
  },
];

const perms = (...values: Permission[]) => new Set<Permission>(values);

describe("visibleNav (IA §4.3)", () => {
  it("hides items without permission and drops empty groups", () => {
    const visible = visibleNav(groups, perms("dashboard.read", "inventory.read"));
    expect(visible.map((group) => group.label)).toEqual([undefined, "Commerce"]);
  });

  it("never links to a page that is not built yet", () => {
    const visible = visibleNav(groups, perms("dashboard.read"));
    expect(visible.flatMap((group) => group.items).map((item) => item.segment)).toEqual(["overview"]);
  });

  it("shows only built pages from the real navigation tree", () => {
    const all = new Set<Permission>(NAV_GROUPS.flatMap((group) => group.items.flatMap((item) => item.permission)));
    const segments = visibleNav(NAV_GROUPS, all).flatMap((group) => group.items.map((item) => item.segment));
    expect(segments).toEqual(
      NAV_GROUPS.flatMap((group) => group.items.filter((item) => item.ready).map((item) => item.segment)),
    );
  });
});

describe("activeNavItem (C-23)", () => {
  it("matches detail pages by prefix", () => {
    expect(activeNavItem(groups, "s1", "/s/s1/inventory/123")?.label).toBe("Inventory");
  });

  it("prefers the longest matching segment", () => {
    expect(activeNavItem(groups, "s1", "/s/s1/inventory/movements")?.label).toBe("Movements");
  });

  it("does not match a sibling that only shares a prefix", () => {
    expect(activeNavItem(groups, "s1", "/s/s1/overview-old")).toBeUndefined();
    expect(activeNavItem(groups, "s2", "/s/s1/overview")).toBeUndefined();
  });
});
