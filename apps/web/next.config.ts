import type { NextConfig } from "next";

// The browser only talks to this origin. `/api/*` is forwarded to FastAPI so the session and
// CSRF cookies stay first-party and no CORS policy is needed (ADR-0004). Rewrites are resolved
// when the server is built, so API_INTERNAL_URL must be set at build time for container images.
const apiOrigin = (process.env.API_INTERNAL_URL ?? "http://localhost:8000").replace(/\/+$/, "");

// Baseline browser hardening for every page (SECURITY_ARCHITECTURE §13). The CSP directives here
// do not restrict scripts or styles, so they are safe with the framework's inline bootstrap; a
// nonce-based script policy is a separate, tested change.
const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
  {
    key: "Content-Security-Policy",
    value: "frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'",
  },
];

const nextConfig: NextConfig = {
  // Self-contained server (`.next/standalone`) for the container image (infra/docker/web.Dockerfile).
  output: "standalone",
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
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiOrigin}/api/:path*` }];
  },
};

export default nextConfig;
