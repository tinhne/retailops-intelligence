"use client";

import { Menu, WifiOff } from "lucide-react";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { useMediaQuery, useOnline, useStoredBoolean } from "@/lib/hooks/browser";
import { useStore } from "@/lib/store/store-context";

import { DemoBanner } from "./demo-banner";
import { activeNavItem, NAV_GROUPS, visibleNav } from "./nav-config";
import { NavList, Sidebar } from "./sidebar-nav";
import { StoreSwitcher } from "./store-switcher";
import { UserMenu } from "./user-menu";

const SIDEBAR_COLLAPSED_KEY = "ro.sidebar.collapsed";

function Wordmark({ compact = false }: { compact?: boolean }) {
  return compact ? (
    <span aria-label="RetailOps Intelligence" className="text-title">
      R
    </span>
  ) : (
    <span className="truncate text-title">RetailOps</span>
  );
}

/**
 * The authenticated frame (COMPONENT_INVENTORY C-20, SCREEN_SPECIFICATIONS §0.2): skip link,
 * demo banner, sidebar (drawer below 768 px, icon rail at 768–1023 px), top bar and main region.
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const store = useStore();
  const pathname = usePathname();
  const online = useOnline();
  const isDesktop = useMediaQuery("(min-width: 1024px)");
  const [collapsed, setCollapsed] = useStoredBoolean(SIDEBAR_COLLAPSED_KEY, false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const liveRegion = useRef<HTMLDivElement>(null);
  const previousPath = useRef(pathname);

  const groups = visibleNav(NAV_GROUPS, store.permissions);
  const active = activeNavItem(groups, store.id, pathname);
  const section = active?.segment ?? "overview";
  const rail = !isDesktop || collapsed;

  // After client-side navigation, move focus to the page h1 and announce the new title.
  useEffect(() => {
    if (previousPath.current === pathname) return;
    previousPath.current = pathname;
    const frame = window.requestAnimationFrame(() => {
      document.querySelector<HTMLElement>("#content h1")?.focus();
      if (liveRegion.current) liveRegion.current.textContent = document.title;
    });
    return () => window.cancelAnimationFrame(frame);
  }, [pathname]);

  return (
    <div className="flex min-h-dvh flex-col">
      <a
        href="#content"
        className="sr-only z-(--z-skip-link) rounded-md bg-card px-3 py-2 text-body-strong shadow-popover focus:not-sr-only focus:fixed focus:top-2 focus:left-2"
      >
        Skip to content
      </a>
      <DemoBanner />
      <div className="flex flex-1">
        <Sidebar
          groups={groups}
          storeId={store.id}
          active={active}
          rail={rail}
          canToggle={isDesktop}
          onToggle={() => setCollapsed(!collapsed)}
          header={(isRail) => <Wordmark compact={isRail} />}
          top={<StoreSwitcher section={section} />}
        />
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-(--z-topbar) flex h-(--topbar-h) shrink-0 items-center gap-2 border-b bg-card px-(--page-gutter)">
            <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
              <SheetTrigger asChild>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="md:hidden"
                  aria-label="Open navigation"
                  aria-controls="mobile-navigation"
                  aria-expanded={drawerOpen}
                >
                  <Menu aria-hidden />
                </Button>
              </SheetTrigger>
              <SheetContent
                id="mobile-navigation"
                side="left"
                className="w-[280px] max-w-[85vw] gap-0 bg-sidebar p-0"
              >
                <SheetTitle className="sr-only">Navigation</SheetTitle>
                <SheetDescription className="sr-only">Pages in {store.name}</SheetDescription>
                <div className="flex h-(--topbar-h) shrink-0 items-center px-5">
                  <Wordmark />
                </div>
                <div className="px-3">
                  <StoreSwitcher section={section} />
                </div>
                <nav aria-label="Main" className="min-h-0 flex-1 overflow-y-auto">
                  <NavList
                    groups={groups}
                    storeId={store.id}
                    active={active}
                    rail={false}
                    onNavigate={() => setDrawerOpen(false)}
                  />
                </nav>
              </SheetContent>
            </Sheet>
            <span className="truncate text-body-strong md:hidden">{store.name}</span>
            {active ? (
              <nav aria-label="Breadcrumb" className="hidden text-sm md:block">
                <span aria-current="page" className="text-foreground">
                  {active.label}
                </span>
              </nav>
            ) : null}
            <div className="ml-auto flex items-center gap-1">
              <UserMenu />
            </div>
          </header>
          {online ? null : (
            <div role="status" className="flex items-center gap-2 border-b bg-tone-neutral-bg px-(--page-gutter) py-2 text-sm text-tone-neutral-fg">
              <WifiOff aria-hidden className="size-4" />
              You&apos;re offline. Data shown may be out of date.
            </div>
          )}
          <main id="content" tabIndex={-1} className="flex-1 outline-none">
            <div className="mx-auto w-full max-w-(--content-max) px-(--page-gutter) py-6">{children}</div>
          </main>
          <div ref={liveRegion} aria-live="polite" className="sr-only" />
        </div>
      </div>
    </div>
  );
}
