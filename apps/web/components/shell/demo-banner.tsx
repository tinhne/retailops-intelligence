"use client";

import { Button } from "@/components/ui/button";
import { useStore } from "@/lib/store/store-context";
import { useLogout } from "@/lib/session/session";

/**
 * Makes seeded data unmistakable on every page of a demo organization (COMPONENT_INVENTORY C-21).
 * Not dismissible. "Take the tour" arrives with the tour panel (C-93), so it is not rendered yet.
 * The spec's "periodically reset" is added once the demo reset job exists (T-094).
 */
export function DemoBanner() {
  const store = useStore();
  const logout = useLogout();

  if (!store.organization.isDemo) return null;

  return (
    <div
      role="region"
      aria-label="Demo notice"
      className="flex h-(--demo-banner-h) shrink-0 items-center gap-3 bg-demo-banner px-(--page-gutter) text-sm text-demo-banner-foreground"
    >
      <p className="min-w-0 flex-1 truncate">
        <strong className="font-semibold">Demo data</strong>
        <span className="sm:hidden"> · read-only</span>
        <span className="hidden text-demo-banner-muted sm:inline">
          {" "}
          {store.name} is a fictional store. All records are generated.
          {store.role === "VIEWER" ? " You are signed in as a read-only viewer." : null}
        </span>
      </p>
      <Button
        type="button"
        variant="link"
        size="sm"
        className="text-demo-banner-foreground underline hover:text-demo-banner-foreground"
        pending={logout.isPending}
        pendingLabel="Leaving…"
        onClick={() => logout.mutate()}
      >
        Leave demo
      </Button>
    </div>
  );
}
