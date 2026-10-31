"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo } from "react";

import { AppShell } from "@/components/shell/app-shell";
import { ErrorState } from "@/components/states/error-state";
import { NotFoundState } from "@/components/states/not-found-state";
import { Skeleton } from "@/components/ui/skeleton";
import { isApiError } from "@/lib/api/errors";
import { readLastStoreId, writeLastStoreId } from "@/lib/session/navigation";
import { defaultStoreId, useMe } from "@/lib/session/session";
import { resolveStoreContext, StoreProvider } from "@/lib/store/store-context";

/** Skeleton of the shell while the session or store resolves. */
export function FullPageLoading() {
  return (
    <div aria-busy="true" className="flex min-h-dvh">
      <span className="sr-only" role="status">
        Loading your workspace
      </span>
      <div className="hidden w-(--sidebar-w) border-r bg-sidebar p-4 lg:block">
        <Skeleton className="h-6 w-28" />
      </div>
      <div className="flex-1">
        <div className="h-(--topbar-h) border-b bg-card" />
        <div className="flex flex-col gap-4 p-(--page-gutter)">
          <Skeleton className="h-7 w-48" />
          <Skeleton className="h-24 w-full" />
        </div>
      </div>
    </div>
  );
}

/**
 * Requires a session for everything under `(app)` (IA §4.1). A 401 is handled globally by
 * the query client (redirect to sign-in), so it only keeps the loading state meanwhile.
 */
export function SessionGate({ children }: { children: React.ReactNode }) {
  const me = useMe();

  if (me.isPending) return <FullPageLoading />;
  if (me.isError) {
    if (isApiError(me.error) && me.error.status === 401) return <FullPageLoading />;
    return (
      <main id="content">
        <ErrorState size="page" title="Couldn't load your workspace" error={me.error} onRetry={() => me.refetch()} />
      </main>
    );
  }
  return children;
}

/** `/`: the last-used store if still accessible, else the first one (IA §4.2). */
export function HomeRedirect() {
  const { data: me } = useMe();
  const router = useRouter();
  const storeId = me ? defaultStoreId(me, readLastStoreId()) : undefined;

  useEffect(() => {
    if (storeId) router.replace(`/s/${storeId}/overview`);
  }, [storeId, router]);

  if (me && !storeId) {
    return (
      <main id="content" className="mx-auto max-w-md py-16 text-center">
        <h1 className="text-title">No store yet</h1>
        <p className="mt-2 text-body text-muted-foreground">
          Your account isn&apos;t a member of any store. Ask an owner to add you.
        </p>
      </main>
    );
  }
  return <FullPageLoading />;
}

/** Resolves the `storeId` segment against `/auth/me` and renders the app shell (IA §7). */
export function StoreShell({ children }: { children: React.ReactNode }) {
  const { storeId } = useParams<{ storeId: string }>();
  const { data: me } = useMe();
  const store = useMemo(() => (me ? resolveStoreContext(me, storeId) : undefined), [me, storeId]);

  useEffect(() => {
    if (store) writeLastStoreId(store.id);
  }, [store]);

  if (!me) return <FullPageLoading />;
  if (!store) {
    return (
      <main id="content">
        <NotFoundState entity="store" />
      </main>
    );
  }
  return (
    <StoreProvider value={store}>
      <AppShell>{children}</AppShell>
    </StoreProvider>
  );
}
