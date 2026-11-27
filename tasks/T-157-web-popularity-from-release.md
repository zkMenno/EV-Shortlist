# T-157 Web reads popularity from the release; unpack the photo bundle
Role: builder   Lane: apps/web (WS2)   Wave: launch
Status: doing (batch: T-157, 2026-11-27)

## Goal
The web ranking uses the release's own popularity figures instead of its own script, and the build can read photos from the new bundle.

## Acceptance criteria
- [x] `apps/web/scripts/popularity.mjs` reads `generations[].popularity` from the release (T-149) instead of computing its own; same ranking within the back-test tolerance (Spearman ≥ 0.95 vs today, number in the PR body). Old releases without the field still build (D5 N-1).
- [x] `apps/web/scripts/fetch-release.mjs` unpacks (done now, ahead of T-146, so the photo path is ready when rows need it) `images.tar` when the release has one (Decision 086) and checks each file's sha256 from the manifest; releases 1–3 without a bundle still work.
- [x] When a row has `dc_speed_is_claim: true`, the claim badge (as for `dc_peak_kw_is_claim`) shows on dc_avg_10_80_kw, dc_minutes_10_80, dc_km_per_10min and dc_km_per_20min; carry the field in `apps/web/src/lib/explore-data.ts`; unit test with a fixture row.
- [x] **G-69 (T-167 retro):** `apps/web/scripts/budget.mjs` prints a clear warning when the client catalogue exceeds 85 % of its 300 KB gzip budget (`255 KB`), without changing the 300 KB failure threshold; unit test covering warn vs pass vs fail.
- [x] Unit tests with fixtures; web lint, types, tests, build, budget, and e2e green locally first.

## Inputs
WS0 INBOX 2026-11-19 03:02 UTC (batch: #171/T-149/T-150, item 5) & 2026-11-27 06:31 UTC (batch: T-167 retro → G-69); Decision 086; T-149, T-150 Handoff notes.

## Out of scope
Showing photos in rows (T-146).

## Handoff notes
- **Release popularity (`scripts/popularity.mjs`, `src/lib/popularity.ts`, `src/lib/catalogue.ts`, `src/app/[country]/[lang]/cars/page.tsx`, `scripts/budget.mjs`):**
  - `scripts/popularity.mjs` reads `generations[].popularity` from `data/releases/<latest>/catalogue.json` (`schema: "popularity-release/v1"`), keeping blend weights from `config/popularity.yaml` (or existing JSON weights in Docker contexts). Older releases (1–3) without `generations[].popularity` fall back to `data/seed/top40.yaml` + `data/editorial/menno-picks.yaml` (`schema: "popularity-inputs/v1"`, D5 N-1).
  - `src/lib/popularity.ts` exports `releasePopularity()`, `releasePopularityAsOf()`, `generatedAsOf()`, and `resolvePopularity()`. `JsonCatalogue.popularity()` and `scripts/budget.mjs` read `generations[].popularity` directly from the loaded release and fall back cleanly on N-1 releases or the dev fixture; `cars/page.tsx` reads `cat.popularityAsOf()` (`2026-11-27` on release 4).
  - Measured on release 4 vs today's web ranking (`rankGenerations` on `top40.yaml` + `menno-picks.yaml`): **Spearman ρ = 0.9522** (≥ 0.95) across all 87 overlapping generations (release 4 ranks 156 generations total, 0 rank inversions, top 3: Tesla Model Y `87.2`, Tesla Model 3 `80.0`, Skoda Enyaq `55.8`).
- **Photo bundle unpack (`scripts/fetch-release.mjs` + `fetch-release.d.mts` + `src/lib/fetch-release.test.ts`):**
  - Pure-Node USTAR/POSIX tar parser (`parseTar`) + strict `unpackBundle()` verifying the tar checksum, regular-file-only members under `bundle.folder`, no unexpected/duplicate/missing members, and every unpacked file's bytes + sha256 atomically.
  - Default runs fetch and unpack `images.tar` when the release manifest has a photo bundle (Decision 086); local `images.tar` repairs missing/corrupted photos without re-downloading. Releases 1–3 without a bundle continue working unchanged.
  - Verified live on release 4: downloaded `images.tar`, verified sha256, unpacked and sha256-checked all 357 WebP photos into `data/releases/4/images/`; re-runs in `auto` and `manifest` modes both report ready.
- **`dc_speed_is_claim` badge (`src/lib/dc.ts`, `src/lib/explore-data.ts`, `SpecValue.tsx`, `Explore.tsx`, `top/[list]/page.tsx`):**
  - Added `DC_SPEED_CLAIM_KEYS` and `isClaimField(row, key)` in `src/lib/dc.ts`; carried `dc_speed_is_claim` in `EXPLORE_FIELDS`.
  - Wired `isClaimField()` into `SpecValue.tsx` (variant, generation diff, compare), `Explore.tsx` (`num()` table cells + `spanNum()` cards), and `top/[list]/page.tsx`. Verified on real release 4 claim rows (Skoda Elroq 85, Hyundai Ioniq 5 facelift base/awd, Ford e-Tourneo Courier 46 kWh).
- **G-69 budget warning (`scripts/budget.mjs`, `budget.d.mts`, `src/lib/budget.test.ts`):**
  - Added `CATALOGUE_WARN_RATIO = 0.85`, `CATALOGUE_WARN_KB = 255`, and `evaluateCatalogueBudget()`; emits `::warning::Perf budget: ...` strictly above 255 KB while keeping the 300 KB failure threshold unchanged.
  - Release 4 client catalogue measured at **171.0 KB gzip** (`2973.3 KB raw`, 57.0 % of 300 KB budget); Landing first-load JS **172.4 KB**, Explore `/cars` **168.8 KB** (both < 200 KB).

## Review

