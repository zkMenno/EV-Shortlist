# AGENTS.md — infra/

Lane rules for deploy config. Read the root `AGENTS.md` first; this file only adds to it.

`infra/` holds the files that run EV Finder on Menno's shared AppInfra server (Hetzner CAX31,
Arm, 16 GB, shared with GardenLayer and Dungeon Tracker). See DECISIONS.md 005 and 006.

## Layout

```
infra/
  AGENTS.md            this file
  README.md            server overview, CI staging deploy status, and reference runbook
  deploy/              reference only (AppInfra is source of truth for ev-staging since #88)
    compose.ev.yml     ev-web, ev-web-staging, ev-jobs (one-shot, profile "jobs")
    ev.caddy           site blocks imported by the server's Caddy
```

Image build files live with their code: `apps/web/Dockerfile`, `pipeline/Dockerfile`, and
`.github/workflows/images.yml` builds both for linux/arm64, pushes them to GHCR, and deploys
`ev-staging` (`staging.evshortlist.com`) on push to `main`.

## Rules (non-negotiable)

1. **Agents never apply anything by hand.** No `ssh`, no `docker compose up` against the server, no
   Caddy reloads, no DNS changes, no AppInfra edits. Agents write files; Menno applies AppInfra
   and live (`ev`) changes (`infra/README.md`). **CI exception (#88/#89/#94):**
   `.github/workflows/images.yml` (`deploy-staging` job, using Menno's deploy key in the
   `staging` environment) deploys `ev-staging` automatically after `smoke-web` passes on `main`.
   Local tests on throwaway containers are fine.
2. **No secrets, ever.** Env files are referenced by path (`/srv/ev/env/*.env`) and live only
   on the server. Variable names go in `.env.example`. No tokens, hashes, IPs, hostnames of the
   real server, or the real domain until it is decided.
3. **Limits per Decision 006** (change them only with a new decision; AppInfra runs `ev-staging`
   at `384 MB` since #88, while reference `compose.ev.yml` keeps `256 MB`):

   | Service | Memory | CPU | Notes |
   |---|---|---|---|
   | `ev-web` | 768 MB | 1.0 | always on |
   | `ev-web-staging` | 256 MB (reference) / 384 MB (AppInfra `ev-staging`) | 0.5 | always on |
   | `ev-jobs` | 1 GB | 1.0 | low priority (`cpu_shares: 256`, `oom_score_adj: 500`), nightly only, 🟡 00:30–02:30 UTC to confirm (Q-001) |

   `memswap_limit` equals `mem_limit` (no swap headroom).
4. **No database container.** EV Finder uses its own database and login in the shared
   Postgres 17 + PostGIS, reached over its private network. Pool budget: ~10 live, 3 staging,
   3 jobs.
5. **Hardened by default:** `read_only` root filesystem (tmpfs for the few writable paths),
   `no-new-privileges`, `cap_drop: ALL`, non-root users in the images, healthchecks, restart
   policy, json-file log rotation (10 MB × 3).
6. **No ports published.** Only Caddy reaches the web containers, over the shared proxy network.
7. **Images come from CI only** (Decision 005): `ghcr.io/zkmenno/ev-finder-web` and
   `ghcr.io/zkmenno/ev-finder-jobs`, linux/arm64. Never build on the server.
8. **Security headers live in two places:** `apps/web/next.config.ts` and `deploy/ev.caddy`.
   Keep the CSPs in step: Caddy's (deferred) copy replaces the app's and may only be stricter
   (today it adds `object-src 'none'`).
9. Mark anything unconfirmed with 🟡 and point to the question in `QUESTIONS.md`.

## Checks before a PR

```sh
docker compose -f infra/deploy/compose.ev.yml --profile jobs config --no-env-resolution -q
docker run --rm -v "$PWD/infra/deploy/ev.caddy:/f:ro" caddy:2 caddy adapt --config /f --validate
```
