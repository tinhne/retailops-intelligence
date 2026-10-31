import type { NextConfig } from "next";

// The browser only talks to this origin. `/api/*` is forwarded to FastAPI so the session and
// CSRF cookies stay first-party and no CORS policy is needed (ADR-0004). Rewrites are resolved
// when the server is built, so API_INTERNAL_URL must be set at build time for container images.
const apiOrigin = (process.env.API_INTERNAL_URL ?? "http://localhost:8000").replace(/\/+$/, "");

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  poweredByHeader: false,
  experimental: {
    // Everything behind sign-in renders in the browser once `/auth/me` answers (TanStack Query
    // owns data fetching, IA §4.1), so the server cannot prerender it to validate instant
    // navigation. Validate only segments that opt in with `export const instant`.
    instantInsights: { validationLevel: "manual-warning" },
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async redirects() {
    // `/s/{storeId}` has no page of its own (IA §4.2).
    return [{ source: "/s/:storeId", destination: "/s/:storeId/overview", permanent: false }];
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiOrigin}/api/:path*` }];
  },
};

export default nextConfig;
