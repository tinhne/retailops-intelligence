"use client";

import { PageHeader } from "@/components/shell/page-header";
import { PermissionDenied } from "@/components/states/permission-denied";
import { useStore } from "@/lib/store/store-context";

/** Overview (SCREEN_SPECIFICATIONS S-02). The dashboard content is built in T-061. */
export function OverviewScreen() {
  const store = useStore();

  if (!store.permissions.has("dashboard.read")) {
    return <PermissionDenied pageName="the overview" permission="dashboard.read" />;
  }

  return <PageHeader title="Overview" subtitle={store.name} />;
}
