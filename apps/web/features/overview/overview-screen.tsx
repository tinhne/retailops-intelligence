"use client";

import { useQuery } from "@tanstack/react-query";
import { Database } from "lucide-react";

import { KpiSkeleton } from "@/components/data/kpi-card";
import { PageHeader } from "@/components/shell/page-header";
import { EmptyState } from "@/components/states/empty-state";
import { ErrorState } from "@/components/states/error-state";
import { PermissionDenied } from "@/components/states/permission-denied";
import { Skeleton } from "@/components/ui/skeleton";
import { ImportLink } from "@/features/imports/import-actions";
import { storeApi, storeKeys, type Dashboard } from "@/lib/api/store-api";
import { formatLongDate } from "@/lib/format/datetime";
import { useDocumentTitle } from "@/lib/hooks/use-document-title";
import { useNow } from "@/lib/hooks/use-now";
import { useStore } from "@/lib/store/store-context";

import { RunAnalysisButton } from "../evaluations/run-analysis-button";
import { AttentionList, CategoryCard, KpiRow, StockHealthCard } from "./dashboard-sections";
import { FreshnessStrip } from "./freshness-strip";
import { RecentImports, TemplateLinks } from "./recent-imports";
import { ShipmentsChart } from "./shipments-chart";

/** No catalog and nothing ever imported: the store has no data yet (S-02 "Empty"). */
export function hasNoData(dashboard: Dashboard): boolean {
  return (
    dashboard.inventory.active_products === 0 &&
    dashboard.active_exceptions.total === 0 &&
    dashboard.data_freshness.imports.every((item) => item.applied_at === null)
  );
}

function DashboardSkeleton() {
  return (
    <div aria-busy="true" className="flex flex-col gap-6">
      <span className="sr-only" role="status">
        Loading overview
      </span>
      <Skeleton className="h-10 w-full max-w-xl" />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {[0, 1, 2, 3, 4, 5].map((card) => (
          <KpiSkeleton key={card} />
        ))}
      </div>
      <div className="grid gap-6 xl:grid-cols-3">
        <div className="flex flex-col gap-3 rounded-lg border bg-card p-5 xl:col-span-2">
          {[0, 1, 2, 3, 4, 5, 6, 7].map((row) => (
            <Skeleton key={row} className="h-10 w-full" />
          ))}
        </div>
        <div className="flex flex-col gap-6">
          <Skeleton className="h-56 w-full" />
          <Skeleton className="h-56 w-full" />
        </div>
      </div>
    </div>
  );
}

/**
 * Overview (SCREEN_SPECIFICATIONS S-02): what needs attention now, is someone on it, and is the
 * data current. The KPI row, attention list and side cards come from one dashboard call and fail
 * together; the chart and recent imports load and fail independently.
 */
export function OverviewScreen() {
  const store = useStore();
  const now = useNow();
  useDocumentTitle("Overview");
  const allowed = store.permissions.has("dashboard.read");

  const dashboard = useQuery({
    queryKey: storeKeys.dashboard(store.id),
    queryFn: ({ signal }) => storeApi.dashboard(store.id, signal),
    enabled: allowed,
  });

  if (!allowed) return <PermissionDenied pageName="the overview" permission="dashboard.read" />;

  const running = dashboard.data?.data_freshness.last_evaluation_run?.status === "RUNNING";
  const canReadImports = store.permissions.has("imports.read");

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Overview"
        subtitle={formatLongDate(now, store.timezone)}
        actions={<RunAnalysisButton running={running} />}
      />

      {dashboard.isPending ? (
        <DashboardSkeleton />
      ) : dashboard.isError ? (
        <div className="rounded-lg border bg-card">
          <ErrorState title="Couldn't load the overview" error={dashboard.error} onRetry={() => void dashboard.refetch()} />
        </div>
      ) : hasNoData(dashboard.data) ? (
        <div className="rounded-lg border bg-card">
          <EmptyState
            size="page"
            icon={Database}
            title="No data yet"
            description={
              store.permissions.has("imports.run")
                ? "Import products first, then inventory adjustments, orders and order items, to start detecting exceptions."
                : "Ask an owner or manager to import data."
            }
            action={
              <div className="flex flex-col items-center gap-3">
                <ImportLink type="products" label="Start an import" />
                {canReadImports ? <TemplateLinks /> : null}
              </div>
            }
          />
        </div>
      ) : (
        <>
          <FreshnessStrip freshness={dashboard.data.data_freshness} />
          <KpiRow dashboard={dashboard.data} />
          <div className="grid grid-cols-1 items-start gap-6 xl:grid-cols-3">
            <div className="xl:col-span-2">
              <AttentionList dashboard={dashboard.data} />
            </div>
            <div className="flex flex-col gap-6">
              <CategoryCard dashboard={dashboard.data} />
              <StockHealthCard dashboard={dashboard.data} />
            </div>
          </div>
        </>
      )}

      {dashboard.isSuccess && !hasNoData(dashboard.data) ? (
        <>
          <ShipmentsChart />
          {canReadImports ? <RecentImports /> : null}
        </>
      ) : null}
    </div>
  );
}
