"use client";

import { createContext, useContext } from "react";

import type { MeResponse, Permission, Role } from "@/lib/api/auth";
import { gateFor, type Gate } from "@/lib/permissions";
import { findStoreAccess } from "@/lib/session/session";

/** The store in the URL, resolved against `/auth/me` (IA §7). */
export type StoreContextValue = {
  id: string;
  name: string;
  code: string;
  currency: string;
  timezone: string;
  organization: { id: string; name: string; isDemo: boolean };
  role: Role;
  permissions: ReadonlySet<Permission>;
  user: { id: string; fullName: string; email: string };
};

const StoreContext = createContext<StoreContextValue | null>(null);

/** Builds the context value, or `undefined` when the user has no membership for the store. */
export function resolveStoreContext(me: MeResponse, storeId: string): StoreContextValue | undefined {
  const access = findStoreAccess(me, storeId);
  if (!access) return undefined;
  const { store, membership } = access;
  return {
    id: store.id,
    name: store.name,
    code: store.code,
    currency: store.currency,
    timezone: store.timezone,
    organization: {
      id: membership.organization_id,
      name: membership.organization_name,
      isDemo: membership.is_demo,
    },
    role: membership.role,
    permissions: new Set(membership.permissions),
    user: { id: me.user.id, fullName: me.user.full_name, email: me.user.email },
  };
}

export function StoreProvider({
  value,
  children,
}: {
  value: StoreContextValue;
  children: React.ReactNode;
}) {
  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

export function useStore(): StoreContextValue {
  const value = useContext(StoreContext);
  if (!value) throw new Error("useStore must be used inside a StoreProvider");
  return value;
}

/** Gate for an action in the current store (COMPONENT_INVENTORY §3, `usePermission`). */
export function usePermission(required: Permission | Permission[], extra?: () => Gate): Gate {
  const store = useStore();
  const gate = gateFor(required, { permissions: store.permissions, isDemo: store.organization.isDemo });
  if (!gate.allowed || !extra) return gate;
  return extra();
}
