import { QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { vi } from "vitest";

import { TooltipProvider } from "@/components/ui/tooltip";
import { makeQueryClient } from "@/lib/query/query-client";

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
