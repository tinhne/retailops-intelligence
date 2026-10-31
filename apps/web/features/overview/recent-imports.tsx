"use client";

import { useQuery } from "@tanstack/react-query";
import { FileUp } from "lucide-react";
import Link from "next/link";

import { DateTime } from "@/components/data/values";
import { sectionHref } from "@/components/shell/nav-config";
import { EmptyState } from "@/components/states/empty-state";
import { ErrorState } from "@/components/states/error-state";
import { ImportStatusPill } from "@/components/status/status-pill";
import { Skeleton } from "@/components/ui/skeleton";
import { API_BASE } from "@/lib/api/client";
import { storeApi, storeKeys } from "@/lib/api/store-api";
import { formatCount } from "@/lib/format/number";
import { importTypeLabels, type ImportType } from "@/lib/status-maps";
import { useStore } from "@/lib/store/store-context";

const QUERY = { page_size: 3, sort: "-created_at" };

/** The last three imports (S-02 "Recent imports"). Needs `imports.read`; the caller hides it otherwise. */
export function RecentImports() {
  const store = useStore();
  const query = useQuery({
    queryKey: storeKeys.imports(store.id, QUERY),
    queryFn: ({ signal }) => storeApi.imports(store.id, QUERY, signal),
  });
  const allHref = sectionHref(store.id, "imports", store.permissions);

  return (
    <section aria-labelledby="imports-title" className="rounded-lg border bg-card">
      <div className="flex items-center justify-between gap-2 border-b px-4 py-3 md:px-5">
        <h2 id="imports-title" className="text-title-sm">
          Recent imports
        </h2>
        {allHref ? (
          <Link href={allHref} className="text-sm text-link hover:underline">
            View all imports
          </Link>
        ) : null}
      </div>
      {query.isPending ? (
        <div aria-busy="true" className="flex flex-col gap-3 p-4 md:p-5">
          {[0, 1, 2].map((row) => (
            <Skeleton key={row} className="h-5 w-full" />
          ))}
        </div>
      ) : query.isError ? (
        <ErrorState title="Couldn't load recent imports" error={query.error} onRetry={() => void query.refetch()} />
      ) : query.data.items.length === 0 ? (
        <EmptyState
          icon={FileUp}
          title="No imports yet"
          description="CSV imports of products, orders, order items and inventory adjustments appear here."
        />
      ) : (
        <ul>
          {query.data.items.map((item) => (
            <li
              key={item.id}
              className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b px-4 py-3 text-body last:border-b-0 md:px-5"
            >
              {allHref ? (
                <Link
                  href={`/s/${store.id}/imports/${item.id}`}
                  className="min-w-0 flex-1 basis-48 truncate font-mono text-mono hover:underline"
                  title={item.original_filename}
                >
                  {item.original_filename}
                </Link>
              ) : (
                <span className="min-w-0 flex-1 basis-48 truncate font-mono text-mono" title={item.original_filename}>
                  {item.original_filename}
                </span>
              )}
              <span className="w-40 text-muted-foreground">{importTypeLabels[item.import_type]}</span>
              <ImportStatusPill status={item.status} />
              <span className="w-24 text-right tabular-nums text-muted-foreground">
                {item.row_count === null ? "—" : formatCount(item.row_count, "row")}
              </span>
              <span className="w-36 text-right text-sm text-muted-foreground">
                <DateTime value={item.applied_at ?? item.created_at} compact />
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

const TEMPLATE_TYPES: ImportType[] = ["products", "inventory_adjustments", "orders", "order_items"];

/** CSV template download links (the API serves them; needs `imports.read`). */
export function TemplateLinks() {
  const store = useStore();
  return (
    <p className="flex flex-wrap justify-center gap-x-3 gap-y-1 text-sm">
      <span className="text-muted-foreground">Download CSV templates:</span>
      {TEMPLATE_TYPES.map((type) => (
        <a
          key={type}
          href={`${API_BASE}/stores/${store.id}/imports/templates/${type}`}
          download
          className="text-link hover:underline"
        >
          {importTypeLabels[type]}
        </a>
      ))}
    </p>
  );
}
