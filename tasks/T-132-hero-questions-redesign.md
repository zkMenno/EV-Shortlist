# T-132 Cleaner hero questions and answer chips
Role: builder   Lane: UX (design) then WS2 (build): docs/design/ (UX), apps/web/ hero (WS2)   Wave: launch (staging feedback 2026-11-17)
Status: done (part 1 #145, part 2 #161, batch web 2026-11-18). Follow-ups in T-146.

## Goal
The hero questions, answer chips and results are calm and easy to scan.

## Acceptance criteria
- [ ] UX: designs for 360 and 1280 px: fewer questions on screen at once (one step visible, progress shown), clearer answer chips, a results list that scans in seconds; follows docs/design/brand-design-decisions.md
- [ ] WS2 builds it after UX signs off; same steps and data as launch scope §1; e2e and axe green
- [ ] Before/after screenshots in the PR
- [ ] Verify skill for the lane; evidence pack in the PR; `Verified:` on every commit
- [ ] Fresh review (REVIEW.md from origin/main) passes

## Inputs
docs/spec/feedback-2026-11-17-staging.md item 3

## Out of scope
Anything not on docs/spec/launch-scope.md.

## Handoff notes
- 2026-11-18 (WS2, T-132 part 1 = questions PR): one question per screen. Step in the URL as `q`
  (country · role · trips · charge · area · budget; no `q` = results for a full profile, so old shared
  links still open the top 10). Every step change is a history entry: browser Back = previous question,
  answer kept. Logic in `src/lib/hero-state.ts` (`heroStep`, `nextStep`, `prevStep`, unit tests in
  `hero-state.test.ts`); drawing in `src/components/HeroSteps.tsx` (ProgressRoad, AnswerTrail,
  AnswerTiles); styles `evs-road / evs-opt / evs-trail / evs-qb / evs-seg / evs-cta` in globals.css.
- Keyboard: tap / click / Enter / Space answers and moves on; arrow keys only move the selection.
  Focus goes to the new question's heading. Slide-in 250 ms, none with reduced motion.
- Country tiles: two columns where the name fits next to its tick (≥ ~380 px phones and desktop), one
  column on 360 px phones (two columns split "Netherlands" mid-word). English country names per
  language (`hero.country.<slug>`), not the native names from config.
- "Keep it 8 years" moved into Refine (on the budget step "More filters (optional)", on results "Refine · n").
- Part 2 (results PR, next): phone result rows + desktop table and sidebar, Refine as a bottom sheet
  (reuse #126's sheet once merged), "Show all cars" box inside the results, thumbnails after T-135.
  Results today = the old cards under a new profile bar (name, country · new/used · budget, Edit).
- 2026-11-18 (batch web, T-132 part 2 = results PR): shortlist rows on one grid (`.evs-srow`,
  globals.css): phone = rank, car, compare / price · ❄ winter · ⚡ +km in 20 min / Why / detail line
  (full price sentence + monthly, real range + Official (WLTP), winter note, listings); desktop ≥ 1024 px
  = aligned columns under a head row (#, car, price, winter, in 20 min, why, compare). "Also worth a
  look" and no-price cars = one-line rows (`LineCard`, `.evs-lrow`). Desktop: answers in a sticky
  sidebar (`hero-side`, `hero-answers`, a pencil per answer → that question). "Show all cars" box
  closes the results (`/cars?<answers>&sort=-suggested`). Review nits: N1 arrow-key click = keydown
  flag cleared on keyup/click (no timing), N3 budget field "30,000". Price column uses a hand-rolled
  "€21.4k" (Intl compact differs Node vs browser → hydration error #418).
- Not in part 2 (follow-ups): Refine as a phone bottom sheet (still the `<details>`), photo
  thumbnails (no `generations[].image` in release 2; T-135), a verify flow for the new layout
  (feature-map is a rubric change: own PR, WS0).

## Review
<!-- Reviewer: name, date, head SHA, REVIEW.md items + verdicts. -->
**Fresh reviewer (batch chat https://claude.ai/code/session_01JuyZEY3nUZH3EtZa6ua2od), 2026-11-18, head `a552af9`, REVIEW.md read from origin/main (`7afa832`). Verdict: PASS, 0 must-fix, 1 should-fix, 3 nits. Needs WS0 approval of the feature-map rubric change before merge.**

| Item | Verdict | Evidence |
|---|---|---|
| R0 CI on head | pass | CI run 44296338260 (pull_request, head a552af9): web, e2e (144 passed / 29 skipped), schema, pipeline, audit, gate-guard, ci-ok all success; Images run success. A cancelled workflow_dispatch run on the same SHA (44296397369) is superseded. Branch is **behind main** (#127, #135 merged since): merge main in + re-run CI before merging. |
| R1 conflict markers | pass | `git grep -nE '^(<{7}\|={7}\|>{7})( \|$)' pr145` → none; diff adds none. |
| R2 evidence pack | pass | PR body: verify 11/11, e2e counts, vitest 459, axe on 3 new screens both themes, contrast.py, budget, 6 before/after screenshots (phone + desktop, light + dark). Re-checked locally: tsc 0, eslint 0, vitest 459/459 (54 files, release 2 fetched), `verify --only hero-road-tripper,hero-budget-question,hero-runabout-picker` 3/3 pass (release 2, commit a552af9), `playwright test hero.spec english-only.spec --repeat-each 2` 80 passed / 2 skipped. |
| R3 own checks not weakened | pass, see S1 | Old test "picking answers builds the profile and the URL" replaced by a stricter full walk (focus, Back/Forward, trail, summary). english-only: link-href loop replaced by tile → `/it/en?q=role` (tiles are no longer links). feature-map: `hero-monthly` check moved, not dropped (now in new `hero-budget-question` flow, plus road/step/trail/URL checks); road-tripper gains `hero-summary` "up to €30,000". No skip/only added. |
| R4 launch-scope sentence on published release | pass | Launch scope §1 steps (country, 4-tap profile, budget + ≈ monthly, optional refine) all present; e2e + verify ran on published release 2 (`fetch-release: release 2 verified (sha256)` in CI and locally). Keep-8 add-on kept, moved into Refine as the UX README (staging-r1) specifies. |
| D6 strings | pass | en 864→904 keys; every new key exists in en and in nl/de/fr/es/it (48 added each). Removed in all 6 languages only keys the new UI no longer uses (`hero.q.role/trips/charge/area`, `hero.step1-3`, `hero.stepN`), replaced by `hero.ask.*`/`hero.road.*` with translations kept per language. NL/DE/FR/ES/IT still 12 keys short of en, same as main (pre-existing). No new glossary term. |
| D7 new numbers | n/a | No new data figures; ≈ monthly box is the existing estimate with its labels. |
| D8 UI | pass | Screenshots 360 + 1280, light + dark in PR (evidence branch, 1760×1540 / 2556×1340). axe: 3 new a11y entries (country 360, charge 1280, budget 360) green in CI e2e. New CSS uses tokens only (no hex/rgb in the globals.css diff). 360 px test per question: no overflow, tiles ≥ 56 px, no split labels. Semantics match the UX README: fieldset + radios, `ol` road with `aria-current=step`, trail = buttons. |
| D9 flags/routes | n/a | No flags, routes or nav changed. |
| D10 bundle | pass | CI `budget.mjs`: landing first-load JS 168.8 KB gzip < 200 KB. No dependency changes. |
| D13 network in tests | pass | New tests use local pages only. |

**Should-fix**
- S1: gate-guard (observe) says it *would block* `hero.spec.ts` for `page.waitForTimeout(400)` without a `Test-change:` line. The wait is a legit negative check (arrow key must not advance after the 250 ms delay), but the PR body has a `## Test-change` heading, not the `Test-change:` marker. Add a `Test-change:` line to the PR body (or swap the wait for Playwright's clock) before gate-guard switches to enforce on 2026-11-24.

**Nits**
- N1: `AnswerTiles` tells arrow-key clicks from real clicks with an 80 ms timestamp window (`arrowAt`); works in tests (80/80 with repeat 2) but is timing-based. A `keydown`-flag reset on `click` would be sturdier.
- N2: english-only test now checks one country tile (Italy) instead of every hero country link; consider looping all tiles to keep the old coverage.
- N3: Budget field shows `25000` without a thousands separator (author's stated deviation; the frames show `25,000`).

**Pre-existing (not this PR):** faint vertical light lines through the dark desktop screenshots appear in both before and after frames.

**For WS0:** `apps/web/e2e/feature-map.yaml` is a rubric change (verify flows): reviewed above, no check dropped; needs WS0 approval before merge.
