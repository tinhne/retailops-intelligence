import { QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { vi } from "vitest";

import { TooltipProvider } from "@/components/ui/tooltip";
import type { Permission, Role } from "@/lib/api/auth";
import { makeQueryClient } from "@/lib/query/query-client";
import { StoreProvider, type StoreContextValue } from "@/lib/store/store-context";

/** Renders with a fresh query client (no retries) and the providers the app uses. */
export function renderWithProviders(ui: React.ReactElement) {
  const onSessionExpired = vi.fn();
  const client = makeQueryClient({ onSessionExpired });
  client.setDefaultOptions({ queries: { retry: false }, mutations: { retry: false } });
  const result = render(
    <QueryClientProvider client={client}>
      <TooltipProvider>{ui}</TooltipProvider>
    </QueryClientProvider>,
  );
  return { ...result, client, onSessionExpired };
}

const STORE_ID = "f0da0f22-b9e0-4483-b144-e9f0f8703d13";

/** A store context for screens under `/s/{storeId}` (IA §7). */
export function testStore(options: { permissions?: Permission[]; isDemo?: boolean; role?: Role } = {}): StoreContextValue {
  return {
    id: STORE_ID,
    name: "Kestrel Home & Kitchen",
    code: "KHK",
    currency: "USD",
    timezone: "America/New_York",
    organization: { id: "org-1", name: "Kestrel Commerce", isDemo: options.isDemo ?? false },
    role: options.role ?? "MANAGER",
    permissions: new Set(options.permissions ?? []),
    user: { id: "user-1", fullName: "Priya Raman", email: "manager@kestrel.example" },
  };
}

export function renderInStore(ui: React.ReactElement, store: StoreContextValue = testStore()) {
  return renderWithProviders(<StoreProvider value={store}>{ui}</StoreProvider>);
}
