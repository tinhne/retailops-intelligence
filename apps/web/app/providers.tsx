"use client";

import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { makeQueryClient } from "@/lib/query/query-client";
import { loginPath } from "@/lib/session/navigation";

function createClient(): QueryClient {
  let redirecting = false;
  const client: QueryClient = makeQueryClient({
    // SCREEN_SPECIFICATIONS §0.2 "Session expired": clear cached data, then go to sign-in.
    // A full navigation also drops any in-memory state that belonged to the old session.
    onSessionExpired: (code) => {
      if (redirecting) return;
      redirecting = true;
      client.clear();
      const next = `${window.location.pathname}${window.location.search}`;
      window.location.assign(
        loginPath({ next, reason: code === "SESSION_EXPIRED" ? "expired" : undefined }),
      );
    },
  });
  return client;
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(createClient);

  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        {children}
        <Toaster />
      </TooltipProvider>
    </QueryClientProvider>
  );
}
