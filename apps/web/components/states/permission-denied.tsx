"use client";

import { Lock } from "lucide-react";

import type { Permission } from "@/lib/api/auth";
import { permissionLabels, roleLabels } from "@/lib/permissions";
import { useStore } from "@/lib/store/store-context";

/** Route permission missing inside the shell (SCREEN_SPECIFICATIONS §0.3, C-36). */
export function PermissionDenied({ pageName, permission }: { pageName: string; permission: Permission }) {
  const store = useStore();

  return (
    <div role="status" className="mx-auto flex max-w-md flex-col items-center gap-3 py-16 text-center">
      <span className="flex size-10 items-center justify-center rounded-full bg-muted text-muted-foreground">
        <Lock aria-hidden className="size-6" />
      </span>
      <h1 tabIndex={-1} className="text-title outline-none">
        You don&apos;t have access to {pageName}
      </h1>
      <p className="text-body text-muted-foreground">
        {store.organization.isDemo
          ? "This area isn't part of the read-only demo."
          : `This page requires the ${permissionLabels[permission]} permission. Your role: ${roleLabels[store.role]}.`}
      </p>
    </div>
  );
}
