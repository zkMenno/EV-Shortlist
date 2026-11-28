# T-168 Web image carries the whole release (scores, prices, charging, photos)
Role: builder   Lane: WS4 (apps/web/Dockerfile, .github/workflows/image*.yml)   Wave: launch (blocker for QA launch review)
Status: todo

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

## Review
