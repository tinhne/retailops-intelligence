import {
  ArrowLeftRight,
  Boxes,
  Inbox,
  LayoutDashboard,
  MessageSquareText,
  ScrollText,
  Settings,
  ShoppingCart,
  Tag,
  Upload,
  Users,
  type LucideIcon,
} from "lucide-react";

import type { Permission } from "@/lib/api/auth";

export type NavItem = {
  label: string;
  /** Path below `/s/{storeId}`. */
  segment: string;
  icon: LucideIcon;
  permission: Permission[];
  /**
   * Sidebar entries are not rendered until their page exists (IA §2), so the nav never
   * links to a screen that has not been built.
   */
  ready: boolean;
};

export type NavGroup = { label?: string; items: NavItem[] };

/** The v1 navigation tree (INFORMATION_ARCHITECTURE §2 and §4.3). */
export const NAV_GROUPS: NavGroup[] = [
  {
    items: [
      { label: "Overview", segment: "overview", icon: LayoutDashboard, permission: ["dashboard.read"], ready: true },
    ],
  },
  {
    label: "Operations",
    items: [
      { label: "Exceptions", segment: "exceptions", icon: Inbox, permission: ["exceptions.read"], ready: true },
    ],
  },
  {
    label: "Commerce",
    items: [
      { label: "Orders", segment: "orders", icon: ShoppingCart, permission: ["orders.read"], ready: true },
      { label: "Products", segment: "products", icon: Tag, permission: ["catalog.read"], ready: true },
      { label: "Inventory", segment: "inventory", icon: Boxes, permission: ["inventory.read"], ready: true },
      {
        label: "Movements",
        segment: "inventory/movements",
        icon: ArrowLeftRight,
        permission: ["inventory.read"],
        ready: true,
      },
    ],
  },
  {
    label: "Intelligence",
    items: [
      { label: "Copilot", segment: "copilot", icon: MessageSquareText, permission: ["copilot.use"], ready: false },
    ],
  },
  {
    label: "Data",
    items: [{ label: "Imports", segment: "imports", icon: Upload, permission: ["imports.read"], ready: true }],
  },
  {
    label: "Administration",
    items: [
      { label: "Users & roles", segment: "admin/users", icon: Users, permission: ["users.read"], ready: true },
      { label: "Settings", segment: "admin/settings", icon: Settings, permission: ["settings.read"], ready: true },
      { label: "Audit log", segment: "admin/audit-log", icon: ScrollText, permission: ["audit.read"], ready: true },
    ],
  },
];

/** Items the user may open, without empty groups (IA §4.3). */
export function visibleNav(groups: NavGroup[], permissions: ReadonlySet<Permission>): NavGroup[] {
  return groups
    .map((group) => ({
      ...group,
      items: group.items.filter(
        (item) => item.ready && item.permission.every((permission) => permissions.has(permission)),
      ),
    }))
    .filter((group) => group.items.length > 0);
}

export function navHref(storeId: string, item: NavItem): string {
  return `/s/${storeId}/${item.segment}`;
}

/**
 * The URL of a section page with an optional query, or `undefined` when the page is not built
 * yet or the person lacks its permission. Callers then render plain text instead of a link
 * (S-02 "Actions"), so nothing links to a dead or forbidden page.
 */
export function sectionHref(
  storeId: string,
  segment: string,
  permissions: ReadonlySet<Permission>,
  query?: Record<string, string | string[]>,
): string | undefined {
  const item = NAV_GROUPS.flatMap((group) => group.items).find((candidate) => candidate.segment === segment);
  if (!item || !item.ready || !item.permission.every((permission) => permissions.has(permission))) return undefined;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    for (const entry of Array.isArray(value) ? value : [value]) params.append(key, entry);
  }
  const search = params.toString();
  return `${navHref(storeId, item)}${search ? `?${search}` : ""}`;
}

/**
 * The item for the current path, by longest matching prefix, so `/inventory/movements`
 * highlights Movements rather than Inventory (COMPONENT_INVENTORY C-23).
 */
export function activeNavItem(groups: NavGroup[], storeId: string, pathname: string): NavItem | undefined {
  let best: NavItem | undefined;
  for (const item of groups.flatMap((group) => group.items)) {
    const href = navHref(storeId, item);
    const matches = pathname === href || pathname.startsWith(`${href}/`);
    if (matches && (!best || item.segment.length > best.segment.length)) best = item;
  }
  return best;
}
