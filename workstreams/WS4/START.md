# WS4 lane brief: infra

For any batch chat whose prompt touches this lane. Owner: WS0 (the coordinator). How chats work: [docs/process/README.md](../../docs/process/README.md) §3; rules: [rules.md](../../docs/process/rules.md). The lane writes infra files and copy-paste runbooks; **Menno applies AppInfra / live server changes** (`infra/AGENTS.md` rule 1: agents never ssh or edit AppInfra by hand; staging `ev-staging` deploys automatically from `main` via `.github/workflows/images.yml` `deploy-staging`, #88/#89/#94). The server is Menno's shared Hetzner CAX31 next to GardenLayer and Dungeon Tracker.

## Start
1. Attach the repo with push access (`add_repo zkMenno/EV-Shortlist`, access `push`); add your row to `CHATS.md`. Attach the AppInfra repo too if the prompt says so. Say in your first line which access the chat really has.
2. Read `AGENTS.md`, `REVIEW.md` (from `origin/main`), `docs/process/README.md`, `infra/AGENTS.md`, `infra/README.md`, your task files, this brief, DECISIONS 003, 005, 006, 013, 067.
3. Before each task and again before its first push: check open PRs and `git ls-remote --heads origin | grep <task-id>`; stop if another chat has it (G-41).
4. Spec: `docs/spec/master-spec-v2.md` §13 (hosting), `trip-fit.md` §7 (routing, parked).

## What the lane owns
`infra/`, `pipeline/Dockerfile`, `apps/web/Dockerfile`, `.github/workflows/image*.yml`, and (in the AppInfra repo) the EV Finder entries. App code belongs to WS1/WS2; requests go as one line in `workstreams/WS0/INBOX.md`. `infra/AGENTS.md` and workflow files are gate files: their own PR. Decision numbers: ask WS0 for a sub-range of 070–079.

## Lane rules
- Measure first, then size. Never guess server facts; record measurements with date and time (G-24).
- The shared server comes first: ev-web 768 MB / 1 CPU, staging 384 MB on AppInfra (reference compose 256 MB) / 0.5 CPU, ev-jobs 1 GB / 1 CPU low priority, 00:30–02:30 UTC. Don't touch other apps' services, data or limits; propose changes to their owners.
- Off-site backups (AppInfra #93) must work and be restore-tested before EV Finder holds real user data. Trigger and handoff: ROADMAP.md Phase 0 "Backups".
- No secrets in this public repo; server env files and GitHub secrets only.
- Money over ~€50/month or €200 one-off, irreversible steps (volumes, databases, public DNS) and the brand domain go to Menno via WS0's INBOX. The Valhalla box (~€5–15/month, parked) is within remit once the sizing test shows its size.
- Every server change is written down in `infra/README.md` or the AppInfra README the same day, with rollback.

## Verify before every push
- Caddy: `caddy adapt --validate` on `infra/deploy/ev.caddy` (Docker Hub may rate-limit locally; a CI job for it is an accepted proposal, open as a gate-only PR).
- Compose: `docker compose -f infra/deploy/compose.ev.yml config`. Image changes: the Images workflow on the PR head (smoke-web, arm64 build).
- Commits end with `Verified: <how>`.

## Gotchas
- Staging (staging.evshortlist.com) deploys from every push to `main`: images.yml push → smoke-web → deploy-staging. Note-only commits must not trigger image builds (G-40, `paths-ignore`).
- The web image fetches the release catalogue by manifest (#105); release files are not in git.
- GHCR `ev-finder-web` and `ev-finder-jobs` pull anonymously (public).

## Done (per task)
Change written, measured where possible · documented in the README with rollback · PR with evidence · Status + Handoff notes in the task file · fresh review before merge · numbers in the WS0 INBOX line.

## Finish the batch
State lives in task files and PRs, not here. When the batch is done or blocked: one line in `workstreams/WS0/INBOX.md` (`- YYYY-MM-DD HH:MM UTC · from <chat link> · …`, with the four retro answers or a link to them), then stop. No STATUS or HANDOFF files.

## Open lane threads (current queue lives in BOARD.md and workstreams/WS0/HANDOFF.md)
- `.github/workflows/images.yml` `paths-ignore` ignores `docs/**`, but the web image reads `docs/design/**` (token/font changes don't rebuild staging; #207 follow-up).
- Live (`ev`) waits for Menno's "launch"; then Q-001 busy-evening numbers (`docker stats`, memory, load, disk; upgrade trigger >10 GB or >70 % CPU for weeks), EV database + Postgres checks (`pg_trgm`, PostGIS), off-site backups with one restore test.
- Monitoring: `/health` in the watchdog, disk and memory alerts, monthly check of email and Actions usage.
- Parked after launch: T-037 Valhalla sizing test (NL+BE+LU+DE+FR+UK tiles on a temporary machine).
