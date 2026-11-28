# syntax=docker/dockerfile:1
# EV Finder web image (T-013, Decisions 005, 006, 008).
# Build context = repo root:
#   docker buildx build --platform linux/arm64 -f apps/web/Dockerfile -t ev-finder-web .
# Built in CI (.github/workflows/images.yml) for linux/arm64; never on the shared server.

ARG NODE_VERSION=22
# Public origin for canonical, hreflang and sitemap URLs (A-05 F3). Static pages bake it in at
# build time, so it must be a build arg; `pnpm build` fails without a public https origin.
# CI passes the repo variable APP_URL, else https://evshortlist.com (infra/README.md "APP_URL", #88).
ARG APP_URL

# ---- base: Node + pnpm (version from "packageManager" in package.json, via corepack) ----
FROM node:${NODE_VERSION}-slim AS base
ENV PNPM_HOME=/pnpm \
    PATH=/pnpm:$PATH \
    COREPACK_ENABLE_DOWNLOAD_PROMPT=0 \
    NEXT_TELEMETRY_DISABLED=1
RUN corepack enable
WORKDIR /repo

# ---- deps: install only what @ev/web needs, from the workspace lockfile ----
FROM base AS deps
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml .npmrc tsconfig.base.json ./
COPY apps/web/package.json apps/web/
COPY packages/schema/package.json packages/schema/
# Optional secret `extra_ca`: a CA bundle for builds behind a TLS-intercepting proxy
# (`--secret id=extra_ca,src=ca.crt`). Not needed in CI; never stored in a layer.
RUN --mount=type=cache,id=pnpm-store,target=/pnpm/store \
    --mount=type=secret,id=extra_ca,required=false \
    NODE_EXTRA_CA_CERTS=$([ -f /run/secrets/extra_ca ] && echo /run/secrets/extra_ca) \
    pnpm install --frozen-lockfile --filter "@ev/web..."

# ---- catalogue: every run-time file of the latest release (data/releases/<latest>) ----
# T-168: catalogue.json alone left staging without scores, used prices, charging stats, the
# manifest and photos ("ranking not available", 28 Nov 2026). pack-release.mjs takes the list from
# DEFAULT_FILES in fetch-release.mjs (+ manifest.json, README.md, the unpacked images/ folder),
# checks every listed file's size + sha256 against the manifest and fails the build on a gap.
# images.tar itself stays out of the image (its unpacked files are what the app serves).
FROM node:${NODE_VERSION}-slim AS catalogue
WORKDIR /pack
COPY apps/web/scripts/fetch-release.mjs apps/web/scripts/pack-release.mjs ./
COPY data/releases /src
RUN node pack-release.mjs /src /out

# ---- build: Next standalone output ----
FROM deps AS build
COPY packages/schema packages/schema
# scripts/listings.mjs reads config/countries/*.yaml (allowed by .dockerignore) and regenerates
# src/config/listings.generated.json. data/sources.yaml is not in the context, so scripts/sources.mjs
# keeps the committed src/config/sources.generated.json (a unit test keeps it in step with the YAML).
COPY config/countries config/countries
COPY apps/web apps/web
# Model / generation / variant / learn pages are static (Decision 015, Q-033/Q-034): they are
# built from the release that ships in this image, so a new release means a new image.
COPY --from=catalogue /out data/releases
ARG APP_URL
ENV APP_URL=${APP_URL}
RUN pnpm --filter @ev/web build
# Image checks (A-05 F3 + F10): the CSP hash manifest made it into the standalone output, and no
# prerendered page carries a localhost URL (canonical, hreflang, sitemap).
RUN set -eu; \
    test -s apps/web/.next/standalone/apps/web/.next/server/csp-hashes.json \
      || { echo "csp-hashes.json missing from the standalone output" >&2; exit 1; }; \
    if grep -rlE 'https?://(localhost|127\.0\.0\.1)' apps/web/.next/server/app --include='*.html' --include='*.body' | head -1 | grep -q .; then \
      echo "a prerendered page contains a localhost URL; check APP_URL" >&2; exit 1; fi; \
    grep -rqF "${APP_URL}/" apps/web/.next/server/app --include='*.html' \
      || { echo "no prerendered page links to APP_URL=${APP_URL}" >&2; exit 1; }

# ---- runtime: standalone server, non-root, read-only friendly ----
FROM node:${NODE_VERSION}-slim AS runtime
ARG APP_URL
# Same origin at run time (robots.txt, sitemap and dynamic pages read it per request). web.env may
# repeat it but must not change it: static pages keep the build-time value.
ENV APP_URL=${APP_URL} \
    NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0 \
    CATALOGUE_DIR=/app/data/releases
WORKDIR /app

# Files stay root-owned (read-only for the app user); only .next/cache is writable,
# so the container also runs with a read-only root filesystem plus a tmpfs there.
COPY --from=build /repo/apps/web/.next/standalone ./
COPY --from=build /repo/apps/web/.next/static ./apps/web/.next/static
COPY --from=catalogue /out ./data/releases
RUN mkdir -p apps/web/.next/cache && chown node:node apps/web/.next/cache

USER node
EXPOSE 3000

# node:*-slim has no curl/wget, so probe /health with Node's fetch.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["node", "-e", "fetch('http://127.0.0.1:'+(process.env.PORT||3000)+'/health').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"]

CMD ["node", "apps/web/server.js"]
