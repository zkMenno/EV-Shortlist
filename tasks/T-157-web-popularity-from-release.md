# T-157 Web reads popularity from the release; unpack the photo bundle
Role: builder   Lane: apps/web (WS2)   Wave: launch
Status: todo (unblocked: data release 4 live #226)

## Goal
The web ranking uses the release's own popularity figures instead of its own script, and the build can read photos from the new bundle.

## Acceptance criteria
- [ ] `apps/web/scripts/popularity.mjs` reads `generations[].popularity` from the release (T-149) instead of computing its own; same ranking within the back-test tolerance (Spearman ≥ 0.95 vs today, number in the PR body). Old releases without the field still build (D5 N-1).
- [ ] `apps/web/scripts/fetch-release.mjs` unpacks (done now, ahead of T-146, so the photo path is ready when rows need it) `images.tar` when the release has one (Decision 086) and checks each file's sha256 from the manifest; releases 1–3 without a bundle still work.
- [ ] When a row has `dc_speed_is_claim: true`, the claim badge (as for `dc_peak_kw_is_claim`) shows on dc_avg_10_80_kw, dc_minutes_10_80, dc_km_per_10min and dc_km_per_20min; carry the field in `apps/web/src/lib/explore-data.ts`; unit test with a fixture row.
- [ ] **G-69 (T-167 retro):** `apps/web/scripts/budget.mjs` prints a clear warning when the client catalogue exceeds 85 % of its 300 KB gzip budget (`255 KB`), without changing the 300 KB failure threshold; unit test covering warn vs pass vs fail.
- [ ] Unit tests with fixtures; web lint, types, tests, build, budget, and e2e green locally first.

## Inputs
WS0 INBOX 2026-11-19 03:02 UTC (batch: #171/T-149/T-150, item 5) & 2026-11-27 06:31 UTC (batch: T-167 retro → G-69); Decision 086; T-149, T-150 Handoff notes.

## Out of scope
Showing photos in rows (T-146).

## Handoff notes

## Review
