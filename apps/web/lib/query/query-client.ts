import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";

import { isApiError } from "@/lib/api/errors";

declare module "@tanstack/react-query" {
  interface Register {
    queryMeta: QueryMeta;
    mutationMeta: QueryMeta;
  }
}

type QueryMeta = {
  /** Set on requests where a 401 is an expected answer (the login page's session probe). */
  skipSessionExpiry?: boolean;
};

/** Retry delays for the two automatic retries: 1 s, then 3 s (SCREEN_SPECIFICATIONS §0.3). */
const RETRY_DELAYS_MS = [1000, 3000];

/** Network failures and 5xx responses are retried twice. 4xx answers are final. */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (failureCount >= 2) return false;
  if (!isApiError(error)) return false;
  return error.isNetworkError || error.isServerError;
}

export function retryDelay(attempt: number): number {
  return RETRY_DELAYS_MS[Math.min(attempt, RETRY_DELAYS_MS.length - 1)];
}

type QueryClientOptions = {
  /** Called once for any 401 outside the requests that expect one. */
  onSessionExpired: (code: string) => void;
};

export function makeQueryClient({ onSessionExpired }: QueryClientOptions): QueryClient {
  const handleError = (error: unknown, meta: QueryMeta | undefined) => {
    if (meta?.skipSessionExpiry) return;
    if (isApiError(error) && error.status === 401) onSessionExpired(error.code);
  };

  return new QueryClient({
    queryCache: new QueryCache({ onError: (error, query) => handleError(error, query.meta) }),
    mutationCache: new MutationCache({
      onError: (error, _variables, _context, mutation) => handleError(error, mutation.meta),
    }),
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: true,
        retry: shouldRetry,
        retryDelay,
      },
      mutations: {
        retry: false,
      },
    },
  });
}
