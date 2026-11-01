# syntax=docker/dockerfile:1.7
# RetailOps Intelligence web (Next.js standalone server). Build context = repository root.
#
# API_INTERNAL_URL is a BUILD argument: Next.js compiles the `/api/*` rewrite into the build output
# (routes manifest), so the API origin cannot be changed at run time. Build one image per API
# origin. The value is a server-side address (for example http://api:8000 inside compose) and is
# never exposed to the browser, which only ever talks to this server's origin (ADR-0004).

FROM node:24-alpine AS base
ENV PNPM_HOME=/pnpm \
    NEXT_TELEMETRY_DISABLED=1
ENV PATH="$PNPM_HOME:$PATH"
RUN npm install --global --no-fund --no-audit pnpm@10.33.0
WORKDIR /repo

FROM base AS deps
# Manifests first for layer caching. Only the web app and the contracts package are installed.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/
COPY packages/contracts/package.json packages/contracts/
RUN --mount=type=cache,id=pnpm-store,target=/pnpm/store \
    pnpm config set store-dir /pnpm/store && \
    pnpm install --frozen-lockfile --filter "@retailops/web..."

FROM deps AS build
COPY packages/contracts packages/contracts
COPY apps/web apps/web
ARG API_INTERNAL_URL=http://api:8000
ENV API_INTERNAL_URL=${API_INTERNAL_URL}
RUN pnpm --filter @retailops/web build

FROM node:24-alpine AS runtime
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
WORKDIR /app
# The standalone output mirrors the monorepo layout: the server lives in apps/web/server.js.
COPY --from=build --chown=node:node /repo/apps/web/.next/standalone ./
COPY --from=build --chown=node:node /repo/apps/web/.next/static ./apps/web/.next/static
USER node
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=3s --start-period=15s --retries=3 \
  CMD ["node", "-e", "fetch('http://127.0.0.1:3000/login').then(r=>process.exit(r.ok?0:1),()=>process.exit(1))"]
# exec form: node is PID 1 and receives SIGTERM directly.
CMD ["node", "apps/web/server.js"]
