"use client";

import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

import { navHref, type NavGroup, type NavItem } from "./nav-config";

type NavListProps = {
  groups: NavGroup[];
  storeId: string;
  active?: NavItem;
  /** Icon rail: labels become tooltips and group labels become dividers (DESIGN_SYSTEM §15). */
  rail: boolean;
  onNavigate?: () => void;
};

function NavLink({ item, storeId, current, rail, onNavigate }: {
  item: NavItem;
  storeId: string;
  current: boolean;
  rail: boolean;
  onNavigate?: () => void;
}) {
  const Icon = item.icon;
  const link = (
    <Link
      href={navHref(storeId, item)}
      aria-current={current ? "page" : undefined}
      aria-label={rail ? item.label : undefined}
      onClick={onNavigate}
      className={cn(
        "flex h-8 items-center gap-2 rounded-md text-body-strong text-sidebar-foreground transition-colors duration-100 hover:bg-accent active:bg-muted",
        rail ? "w-10 justify-center" : "px-2",
        current && "bg-sidebar-active text-sidebar-active-foreground hover:bg-sidebar-active",
      )}
    >
      <Icon aria-hidden className={cn("size-4 shrink-0", current && "text-primary")} />
      {rail ? null : <span className="truncate">{item.label}</span>}
    </Link>
  );

  if (!rail) return link;
  return (
    <Tooltip>
      <TooltipTrigger asChild>{link}</TooltipTrigger>
      <TooltipContent side="right">{item.label}</TooltipContent>
    </Tooltip>
  );
}

/** The navigation list shared by the sidebar and the mobile drawer (COMPONENT_INVENTORY C-23). */
export function NavList({ groups, storeId, active, rail, onNavigate }: NavListProps) {
  return (
    <div className={cn("flex flex-col pb-4", rail ? "items-center px-2" : "px-3")}>
      {groups.map((group, index) => (
        <div key={group.label ?? `group-${index}`} className="flex w-full flex-col">
          {group.label ? (
            rail ? (
              <Separator className="my-3" />
            ) : (
              <p className="mt-6 mb-2 px-2 text-overline text-muted-foreground uppercase">{group.label}</p>
            )
          ) : (
            <div className={rail ? "h-3" : "h-2"} />
          )}
          <ul className={cn("flex flex-col gap-0.5", rail && "items-center")}>
            {group.items.map((item) => (
              <li key={item.segment}>
                <NavLink
                  item={item}
                  storeId={storeId}
                  current={active?.segment === item.segment}
                  rail={rail}
                  onNavigate={onNavigate}
                />
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

type SidebarProps = {
  groups: NavGroup[];
  storeId: string;
  active?: NavItem;
  header: (rail: boolean) => React.ReactNode;
  /** Shown above the navigation when expanded (the store switcher). */
  top?: React.ReactNode;
  rail: boolean;
  /** Whether the person can toggle the rail (≥ 1024 px). Below that the rail is fixed. */
  canToggle: boolean;
  onToggle: () => void;
};

/** Expanded (240 px) or rail (56 px) sidebar for ≥ 768 px. */
export function Sidebar({ groups, storeId, active, header, top, rail, canToggle, onToggle }: SidebarProps) {
  return (
    <aside
      className={cn(
        "sticky top-0 hidden h-dvh shrink-0 flex-col border-r border-sidebar-border bg-sidebar transition-[width] duration-200 ease-standard md:flex",
        rail ? "w-(--sidebar-w-collapsed)" : "w-(--sidebar-w)",
      )}
    >
      <div className={cn("flex h-(--topbar-h) shrink-0 items-center", rail ? "justify-center px-2" : "px-3")}>
        {header(rail)}
      </div>
      {top && !rail ? <div className="shrink-0 px-3 pt-2">{top}</div> : null}
      <nav aria-label="Main" className="min-h-0 flex-1 overflow-y-auto">
        <NavList groups={groups} storeId={storeId} active={active} rail={rail} />
      </nav>
      {canToggle ? (
        <div className={cn("flex shrink-0 border-t border-sidebar-border p-2", rail ? "justify-center" : "")}>
          <Button
            type="button"
            variant="ghost"
            size={rail ? "icon" : "sm"}
            onClick={onToggle}
            aria-label={rail ? "Expand sidebar" : "Collapse sidebar"}
            className={rail ? undefined : "w-full justify-start"}
          >
            {rail ? <PanelLeftOpen aria-hidden /> : <PanelLeftClose aria-hidden />}
            {rail ? null : "Collapse"}
          </Button>
        </div>
      ) : null}
    </aside>
  );
}
