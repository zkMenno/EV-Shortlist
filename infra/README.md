# infra/: deploy config for the AppInfra server

> **Status (2026-11-17, issue #88): AppInfra is the source of truth for the server.**
> `ev-staging` (staging.evshortlist.com, public + noindex, no database) is defined in
> zkMenno/AppInfra (#103). Every push to `main` builds the images, smoke-tests the web image under
> the server's limits and runs `deploy ev-staging <full sha>` (`.github/workflows/images.yml`,
> jobs `smoke-web` and `deploy-staging`; secrets in this repo's `staging` environment).
> `deploy/compose.ev.yml` and `deploy/ev.caddy` below are **reference only**: never edit them to
> change the server. Live (`ev`) waits for Menno's "launch".

EV Finder runs on the shared AppInfra server next to GardenLayer and Dungeon Tracker
(Decision 006): the server's Caddy in front, the shared Postgres behind a private network,
and images built in GitHub Actions (Decision 005). Limits per service are fixed by Decision 006
and listed in [`AGENTS.md`](AGENTS.md); agents never apply changes to the server by hand (staging
deploys automatically through `.github/workflows/images.yml` `deploy-staging`).

Check the files locally (no server needed; both pass on 2026-11-15), from the repo root:

```sh
docker compose -f infra/deploy/compose.ev.yml --profile jobs config --no-env-resolution -q
docker run --rm -v "$PWD/infra/deploy/ev.caddy:/f:ro" caddy:2 caddy adapt --config /f --validate
```

(The Caddy check logs failed health probes to `ev-web:3000`; that's expected without the containers.)

## Files

| File | What it is |
|---|---|
| `deploy/compose.ev.yml` | Compose project `ev`: `ev-web` (768 MB / 1 CPU), `ev-web-staging` (256 MB / 0.5 CPU), `ev-jobs` (1 GB / 1 CPU, low priority, one-shot under the `jobs` profile). Read-only root filesystems, no-new-privileges, healthchecks, log rotation. Env from `/srv/ev/env/*.env`. No DB container, no published ports. |
| `deploy/ev.caddy` | Site blocks for `ev.example.com` and `staging.ev.example.com` (**placeholders**: the domain is still open). Reverse proxy, zstd/gzip, HSTS, CSP, nosniff, Referrer-Policy, Permissions-Policy, frame blocking, no `Server` header, long caching for `/_next/static/*` and `/data/catalogue-<n>.json`. |
| `../apps/web/Dockerfile` | Web image: pnpm workspace install → Next standalone build → `node:22-slim` runtime as user `node`. Bakes in only the latest catalogue release (`data/releases/<latest>/catalogue.json`) at `/app/data/releases` (`CATALOGUE_DIR`). HEALTHCHECK on `/health`. |
| `../pipeline/Dockerfile` | Jobs image: `python:3.12-slim` + uv, non-root user `ev`, entrypoint `ev`. Data is mounted at `/data` (`EV_DATA_DIR`). |
| `../.github/workflows/images.yml` | On push to `main` (or by hand): builds both images for linux/arm64 on a native Arm runner and pushes `sha-<short>`, the full sha and `main` tags to GHCR. Passes the `APP_URL` build arg (see below). On `main`: `smoke-web` runs the web image read-only with the staging limits, then `deploy-staging` deploys it to ev-staging and waits for `/health` 200. |
| `../.github/workflows/data-refresh.yml` | Weekly refresh. Job `refresh` (read-only token, not on disk) runs `ev refresh` and uploads the new release folder; job `pr` (write token, runs no pipeline code) checks the artifact, commits only `data/releases/N` + `latest` and opens the PR (A-05 F11). |

`GET /health` returns `{"status":"ok","release":<n or null>,"time":"…"}` with `no-store`. It is
what the AppInfra watchdog, the Docker healthcheck and Caddy's active health check poll. It answers
**503** `{"status":"unhealthy",…}` when the CSP hash manifest (`.next/server/csp-hashes.json`) is
missing from the image (A-05 F10). The site then serves the strict nonce-only policy, never
`'unsafe-inline'`. The image build also fails when the manifest is missing.

### `APP_URL` (public origin, A-05 F3)

Canonical, hreflang, `sitemap.xml` and `robots.txt` URLs are absolute and use `APP_URL`. Model,
generation, variant and learn pages are static, so the origin is **baked in at image build time**:

- `apps/web/Dockerfile` takes `--build-arg APP_URL=…` and sets it at build and run time.
  `pnpm build` (`apps/web/scripts/check-app-url.mjs`) fails when it is missing, not https, or a
  local host. After the build, the Dockerfile fails if a prerendered page contains `localhost` or
  no page links to `APP_URL`.
- `.github/workflows/images.yml` passes `APP_URL=${{ vars.APP_URL || 'https://evshortlist.com' }}`
  (since #88: the domain AppInfra serves). The repository variable `APP_URL` (Settings → Secrets
  and variables → Actions → Variables) overrides it; if set, it must equal the server's `APP_URL`.
- `web.env` on the server may repeat `APP_URL`, but it must have the **same value**: static pages
  keep the build-time origin. The staging container runs the same image, so its canonicals point at
  production (it should stay `noindex` behind Caddy).
- Only throw-away builds may skip it: `CI=true` (CI's own build and e2e jobs) or
  `APP_URL_TEST_BUILD=1`. They fall back to `http://localhost:3000` and are never shipped.

### Git sources (A-05 L6)

Two pipeline sources are fetched with `git clone --depth 1`, not through `ev_pipeline/net.py`:
`openev` (`https://github.com/open-ev-data/open-ev-data-dataset`) and `kilowatt-openev`
(`https://github.com/KilowattApp/open-ev-data`); the refresh probe uses `git ls-remote` on the
same URLs. The URLs are constants in the adapters (`REPO_URL`), https only, on **github.com only**,
which is also the only host in those sources' `hosts:` in `data/sources.yaml`. So net.py's
allowlist, public-IP pinning and size caps do not apply to them; git uses the environment's proxy
settings. Rule: a git source must point at `https://github.com/…`. Adding one on another host
needs a review and an allowlist check before the clone (the A-05 L6 fix: assert the `REPO_URL`
host is in the source's `hosts:` and pass `-c protocol.allow=never -c protocol.https.allow=always`;
pipeline lane). In CI the clone runs in the data-refresh `refresh` job, which has a read-only
token that is not stored on disk (F11).

## Reference manual runbook (superseded for staging by AppInfra + CI)

> Staging (`ev-staging`) now deploys automatically from `main` via `.github/workflows/images.yml` (`deploy-staging`) against the `zkMenno/AppInfra` definition (#88/#89/#94). The checklist below is kept only as a historical reference for manual bring-up or live (`ev`) setup; each 🟡 needs a check first.

1. **Answer the open questions:** Q-001 (capacity, job window), Q-006 (file location), and the
   domain. Replace `ev.example.com` / `staging.ev.example.com` in `deploy/ev.caddy`.
2. **Make the GHCR packages pullable.** After the first `Images` run on `main`, either make
   `ev-finder-web` and `ev-finder-jobs` public in the package settings, or `docker login ghcr.io`
   on the server with a read-only (`read:packages`) token.
3. **Create the folders on the server:**
   ```sh
   sudo mkdir -p /srv/ev/env /srv/ev/data
   sudo chown 10001:10001 /srv/ev/data      # uid of the `ev` user in the jobs image
   sudo chmod 700 /srv/ev/env
   ```
4. **Write the env files** (`/srv/ev/env/web.env`, `web-staging.env`, `jobs.env`, mode 600) from
   the names in `.env.example`. Real values only here, never in the repo. `APP_URL` there must
   equal the image's build arg (see "`APP_URL`" above).
5. **Check the networks** (🟡 names to confirm): the shared Caddy network is assumed to be
   `appinfra-proxy`, EV Finder's private DB network `ev-db`. Adjust the `networks:` block in
   `compose.ev.yml` to the real names (`docker network ls`). The database and login are created
   by AppInfra, not by this file. Nothing uses Postgres yet (Decision 008).
6. **Copy the files** to the server: `compose.ev.yml` → `/srv/ev/compose.ev.yml`,
   `ev.caddy` → `/srv/ev/ev.caddy`.
7. **Start the web containers**, pinning the image tag from the CI run:
   ```sh
   cd /srv/ev
   export EV_WEB_TAG=sha-abc1234 EV_WEB_STAGING_TAG=sha-abc1234
   docker compose -f compose.ev.yml pull ev-web ev-web-staging
   docker compose -f compose.ev.yml up -d ev-web ev-web-staging
   docker compose -f compose.ev.yml ps          # wait for "healthy"
   ```
8. **Hook up Caddy:** add `import /srv/ev/ev.caddy` to the main Caddyfile, then
   `caddy validate` and reload the way AppInfra normally does.
9. **Smoke test:** `curl -sI https://<domain>/health` returns 200 with the security headers;
   `/nl/nl/` loads (URLs are `/{country}/{lang}/…`, Decision 015; `/` and `/nl/` answer with a
   307 redirect to it); `/data/catalogue-<n>.json` has `Cache-Control: … immutable`.
10. **Add the watchdog entry** for `https://<domain>/health` in AppInfra.
11. **Nightly jobs** (🟡 window to confirm, Q-001). Until pg-boss scheduling exists, a host
    timer runs the one-shot container inside 00:30–02:30 UTC, for example a systemd timer with
    `OnCalendar=*-*-* 00:30:00 UTC` running:
    ```sh
    cd /srv/ev && EV_JOBS_TAG=sha-abc1234 timeout 2h \
      docker compose -f compose.ev.yml --profile jobs run --rm ev-jobs release
    ```
    The data folder must hold the pipeline inputs (`seed/`, `sources.yaml`, …); not wired up yet.

**Rollback:** set the previous `sha-…` tag and run step 7 again. Catalogue releases ride in the
web image for now, so a data rollback is an image rollback.

## Next steps (not done)

- Live (`ev`) deploy in AppInfra once Menno gives the go-ahead for launch (staging SSH deploy via CI is live since #88/#89/#94).
- Ensure `.github/workflows/images.yml` rebuilds staging when `docs/design/**` changes (#207 follow-up).
- Serve releases from a mounted `/srv/ev/data/releases` (`CATALOGUE_DIR`) so a data release no
  longer needs a new image.
- Pin base images by digest; add Dependabot `docker` entries for both Dockerfiles.
- Per-request CSP nonces so `script-src` can drop `'unsafe-inline'`.
