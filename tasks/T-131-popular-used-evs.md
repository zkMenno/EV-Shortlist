# T-131 "Popular used EVs" section on the landing
Role: builder   Lane: WS3 (list) + WS2 (section): data/editorial/ (WS3), apps/web/ (WS2)   Wave: launch (staging feedback 2026-11-17)
Status: review (WS3 part; WS3 2nd chat, 2026-11-17). WS2 section: review (WS2 overnight batch, 2026-11-28; builds on T-146 #235 + T-135)

## Goal
The landing shows the popular used EV generations, roughly Menno's own list.

## Acceptance criteria
- [x] WS3: `data/editorial/popular_used.yaml`, generation ids (not trims), seeded from Menno's New Car sheet generations (data/editorial picks, Decision 038) and registration counts; each row says why it is listed
- [x] WS2: landing section renders the list as generation cards (photo once T-135 lands, used price band for the country, winter range)
- [x] Order and contents are data, not code (WS3 side: weights in the file's `method`, rows generated)
- [x] Verify skill for the lane; evidence pack in the PR; `Verified:` on every commit
- [ ] Fresh review (REVIEW.md from origin/main) passes

## Inputs
docs/spec/feedback-2026-11-17-staging.md item 2; data/seed/top40.yaml

## Out of scope
Anything not on docs/spec/launch-scope.md.

## Handoff notes
**WS3 (2026-11-17):** `data/editorial/popular_used.yaml` (33 generations, ordered), built by `data/editorial/build_popular_used.py` (`--check` = stale/unknown-id guard).
- Candidates: Menno's own generation list (menno-picks.yaml `eras`, the eras already on the used market: 2019-2021 … 2024-2026). 2026-2028 (not yet used) left out.
- Order = registration points (41 − model rank in top40.yaml) + owner points (shortlist 20, consider 10, unrated 0, ruled out −10, favourite +5). Unrated generations outside the top 40 are dropped. Weights are written into the file (`method`), reversible default.
- `method.landing_count: 12` = how many the landing shows; the rest belong on the catalogue page.
- Each row has `why` (one plain EN line), `registrations.top40_rank`, `owner.verdict` / `favourite` / `remark`. Owner verdicts must be labelled as one person's opinion (Decision 038).
- Ranks are per model (top40 has no generation split): Niro DE and SG2 share #3.
- Popular models not on Menno's list (Audi Q4 #7, Audi e-tron #11, BMW i4 #14, Mini #15) are not in the section: "roughly his list" (feedback item 2). Say if you want the top 15 models added regardless.
- For WS2: all 33 ids are in release 2, but 6 have no variant rows yet (kia-ev3-gen1, kia-ev6-facelift, opel-astra-electric-gen1, peugeot-e-308-gen1, xpeng-g6-facelift, xpeng-p7-gen1): skip a card with no data rather than show an empty one.

**WS2 (2026-11-28, overnight batch):**
- **Data path:** `apps/web/scripts/popular-used.mjs` reads `data/editorial/popular_used.yaml` and writes `src/config/popular-used.generated.json`. It keeps the order, `generation_id`, `why` and `method.landing_count`; build and dev run it, `--check` exists, and a unit test fails when the JSON is stale. The JSON is committed because the Docker context has no `data/editorial/`, the same pattern as `popularity.mjs`. A missing id or why line, a duplicate, or a bad `landing_count` fails the build.
- **Cards:** `src/lib/popular-used.ts` `popularUsedCards()` makes one generation card per listed id, in list order (shared `generationCards()` from T-130). A listed generation with no variant rows in the release is skipped and the next one moves up, so the landing shows up to `landing_count` (12) cards and never an empty one. On release 4 all 12 show.
- **Section:** `src/components/PopularUsed.tsx` is a server component, so it adds no landing JS (budget: landing 174.5 KB, Explore 169.5 KB gzip).
  - Each card has the photo or placeholder with its credit line (T-135 `CarFigure`), the name linking to the generation page, the years, the list's `why` line, the used band in the visitor's country (with the estimate note), and the real winter range through `<Num>` with provenance plus an ⓘ.
  - The intro labels the owner's picks as one person's opinion (Decision 038) and links "How we pick these" to `/cars#how-we-rank`.
  - It sits between the hero and "Show all cars", and is hidden on the hero results the same way as that box (`.evs-popular`).
- **Strings:** `landing.popular.*` in EN, plus NL/DE/FR/ES/IT so the i18n test passes. The `why` lines are English data from WS3.
- **Also in this PR (T-135 review S1):** `generationTitle()` moved to `src/lib/generation-title.ts` (re-exported from `ev/_lib/data.ts`) and now builds the photo alt on catalogue cards, landing cards and hero row thumbnails, so "Tesla Model Y Model Y" no longer happens; `e2e/photos.spec.ts` checks no card alt repeats a word. T-146 and T-135 task files set to done.
- **Tests:** `e2e/popular-used.spec.ts` checks the list order (a subsequence), each card's why/link/price/winter/photo, that the section hides on results, 360 px with wider letters, and axe in light and dark.

## Review
<!-- Reviewer: name, date, head SHA, REVIEW.md items + verdicts. -->
