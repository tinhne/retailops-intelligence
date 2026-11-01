"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import { authApi, type LoginRequest, type MeResponse, type Membership, type StoreSummary } from "@/lib/api/auth";
import { CSRF_COOKIE, readCookie } from "@/lib/api/client";

import { loginPath } from "./navigation";

export const meQueryKey = ["auth", "me"] as const;
export const authOptionsKey = ["auth", "options"] as const;

/** What this installation offers on the sign-in page: the public demo only where it exists. */
export function useAuthOptions() {
  return useQuery({
    queryKey: authOptionsKey,
    queryFn: ({ signal }) => authApi.options(signal),
    staleTime: 5 * 60_000,
    meta: { skipSessionExpiry: true },
  });
}

/**
 * The current user and memberships. `probe` is for public pages, where a 401 just means
 * "not signed in" and must not trigger the session-expired redirect.
 */
export function useMe(options: { probe?: boolean; enabled?: boolean } = {}) {
  return useQuery({
    queryKey: meQueryKey,
    queryFn: ({ signal }) => authApi.me(signal),
    staleTime: 5 * 60_000,
    enabled: options.enabled ?? true,
    retry: options.probe ? false : undefined,
    meta: options.probe ? { skipSessionExpiry: true } : undefined,
  });
}

/**
 * The API sets the readable CSRF cookie together with the HttpOnly session cookie, so its
 * presence says a session may exist. It is a hint for skipping a pointless request, never a check.
 */
export function hasSessionHint(): boolean {
  return readCookie(CSRF_COOKIE) !== undefined;
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: LoginRequest) => authApi.login(body),
    meta: { skipSessionExpiry: true },
    onSuccess: (me) => {
      queryClient.clear();
      queryClient.setQueryData(meQueryKey, me);
    },
  });
}

export function useDemoLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => authApi.demo(),
    meta: { skipSessionExpiry: true },
    onSuccess: (me) => {
      queryClient.clear();
      queryClient.setQueryData(meQueryKey, me);
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  const router = useRouter();
  return useMutation({
    mutationFn: () => authApi.logout(),
    meta: { skipSessionExpiry: true },
    // Whatever the outcome (an already-expired session answers 401), the person is signed out here.
    onSettled: () => {
      queryClient.clear();
      router.replace(loginPath({ reason: "signed_out" }));
    },
  });
}

export type StoreAccess = { store: StoreSummary; membership: Membership };

/** Finds a store across all memberships. `undefined` means no access (shown as not found, IA §4.2). */
export function findStoreAccess(me: MeResponse, storeId: string): StoreAccess | undefined {
  for (const membership of me.memberships) {
    const store = membership.stores.find((candidate) => candidate.id === storeId);
    if (store) return { store, membership };
  }
  return undefined;
}

/** The store to open after sign-in: the last-used one if still accessible, else the first. */
export function defaultStoreId(me: MeResponse, lastStoreId: string | null): string | undefined {
  if (lastStoreId && findStoreAccess(me, lastStoreId)) return lastStoreId;
  return me.memberships.flatMap((membership) => membership.stores)[0]?.id;
}

export function allStores(me: MeResponse): Array<StoreSummary & { organizationName: string }> {
  return me.memberships.flatMap((membership) =>
    membership.stores.map((store) => ({ ...store, organizationName: membership.organization_name })),
  );
}
