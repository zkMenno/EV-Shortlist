# T-168 Web image carries the whole release (scores, prices, charging, photos)
Role: builder   Lane: WS4 (apps/web/Dockerfile, .github/workflows/image*.yml)   Wave: launch (blocker for QA launch review)
Status: doing (batch: staging fix + web follow-ups, https://claude.ai/code/session_01JuyZEXh24GFZTn2JpiC2bs, 2026-11-28)

## Goal
Staging shows the same hero shortlist and photos as a local build of the latest release.

## Problem (verified 2026-11-28 09:13 UTC)
`https://staging.evshortlist.com/nl/en?role=main&trips=monthly&charge=home&budget=40000` renders `hero-no-scores` ("ranking not available yet") with release 4 live (`/health` ok, release 4); a local `next start` on release 4 shows 10 cards (WS2 overnight, INBOX 2026-11-27 23:05). 🟡 Cause, read from the files: the `catalogue` stage in `apps/web/Dockerfile` copies only `catalogue.json` (+ README) per release, and `.github/workflows/images.yml` fetches with `CATALOGUE_FILES: catalogue.json` (lines 86 and 152). So `shortlist_scores.json`, `used_prices.json`, `charging_stats.json` and `images.tar` / `images/` never reach the image. Photos from T-146/T-135 (served from `<release>/images/` via `/photos/<file>`) stay hidden on staging for the same reason.

## Acceptance criteria
- [ ] The image holds every file the web app reads at run time for the latest release: `catalogue.json`, `shortlist_scores.json`, `used_prices.json`, `charging_stats.json`, `manifest.json`, and the unpacked `images/` folder (via `apps/web/scripts/fetch-release.mjs`, sha256-checked, Decision 086). Use `DEFAULT_FILES` in `apps/web/scripts/fetch-release.mjs` (line 30) as the one list (drop `CATALOGUE_FILES: catalogue.json`); no second hard-coded list in the Dockerfile to drift.
- [ ] A check fails the image build when a file the app reads is missing (e.g. a smoke step that starts the image and asserts the hero URL above has ≥ 1 shortlist row and one `/photos/…` 200), so this can't silently come back.
- [ ] Image size and build time stay reasonable: report before/after (`images.tar` is ~29 MB).
- [ ] After merge + deploy: the staging URL above shows ranked cards and at least one photo with a credit line; screenshot in the PR / task file.
- [ ] Fresh review; `Verified:` on every commit; CI-workflow changes go in their own gate PR (gate-guard).

## Inputs
INBOX 2026-11-27 23:05 (WS2 overnight); Decisions 006, 008, 086; T-157 (`fetch-release.mjs` unpack), T-146, T-135; HANDOFF WS4 note (images.yml ignores `docs/**` but the image reads `docs/design/**`): fix that too if it's a one-liner, else leave a note.

## Out of scope
Pipeline or release format changes; anything on AppInfra production.

## Handoff notes
- **Three PRs, in this order** (so no main run fails in between): (1) gate #240 `images.yml` drops `CATALOGUE_FILES` so the build context gets `DEFAULT_FILES` + the unpacked `images/`; (2) this task PR: `apps/web/Dockerfile` `catalogue` stage runs new `apps/web/scripts/pack-release.mjs`; (3) gate PR: `smoke-web` checks the hero URL has a shortlist and one `/photos/…` answers 200 `image/webp`.
- **One list:** `pack-release.mjs` imports `DEFAULT_FILES` from `fetch-release.mjs` and adds only what isn't a "wanted" file: `manifest.json`, `README.md` and the photo bundle's members (read from the manifest, `bundle.folder = images/`). Every file the manifest lists must be on disk with its size + sha256, else the image build fails (`release 4 is incomplete for the web image: shortlist_scores.json is missing …`). Files an older release doesn't list only warn (same as fetch-release). `images.tar` stays out of the image and the build context (`.dockerignore`).
- Cross-lane: `apps/web/scripts/pack-release.mjs` (+ `.d.mts`, unit test `src/lib/pack-release.test.ts`) sit in WS2's folder because they reuse `DEFAULT_FILES`; flagged in the PR and the INBOX line.
- **Local evidence (amd64 docker, 2026-11-28 ~09:28 UTC):** build 331 s cold; image run read-only at 384 MB / 0.5 CPU: `/health` release 4; hero URL HTML has `hero-shortlist` ×1, `hero-no-scores` ×0, `photo-credit` ×5, `car-thumb` ×5; `/photos/tesla-model-3-highland-4b5840df-400.webp` → 200 `image/webp` 8944 B. Release layer 47.5 MB (was catalogue.json only, ~12 MB); image 3.74 GB (GHCR `main`, arm64) → 3.86 GB local. 🟡 Pre-existing: the standalone layer alone is 2.88 GB (prerendered pages), worth a look by WS4/WS2 later, not in scope.
- `manifest.json` was also missing from the image before, so `/data` (open-data downloads) had no bundle on staging; fixed by the same change.
- HANDOFF note "images.yml ignores `docs/**` but the image reads `docs/design/**`": 🟢 not true for the image. `.dockerignore` keeps `docs/` out of the build context; tokens and scenes are generated into committed files under `apps/web/src` (`pnpm theme`, `scripts/scenes.mjs`), which do trigger a build. No change needed.

## Review
