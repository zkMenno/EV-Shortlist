# T-146 Hero results: phone Refine sheet, row photos, a feature-map flow for the results

Role: builder   Lane: WS2 (apps/web)   Wave: launch
Status: review (WS2 overnight batch, 2026-11-27; gate PR #234, feature PR below)

## Goal
Follow-ups from T-132 (parts 1 #145 and 2 #161), decided by the coordinator 2026-11-18.

## Acceptance criteria
- [x] **Refine on phones as a bottom sheet** (≤ 640 px): same controls as the desktop answers sidebar, opens from the results, keeps focus inside, closes with Esc / back / swipe-down, answers stay in the URL. Desktop sidebar unchanged.
- [x] **Photo thumbnails on shortlist rows** from `generations[].image` (Decision 081; smallest width, lazy, fixed aspect ratio so rows don't jump, alt text "<make model generation>", credit reachable). Only when the release carries images (release 3+); rows without an image keep today's layout. Skip this item if no published release has images yet and say so in the PR.
- [x] **Feature-map flow `hero-results`** for the results layout (rows, "also worth a look", answers sidebar edit, Show all cars box): a rubric change in its own gate PR, approved by the coordinator in advance (adds a check, drops none).
- [x] 360/1280 px, light + dark, plus one run with ~6 % wider letters; axe clean; e2e for the sheet; evidence pack; fresh review; "Verified:" on every commit.

## Inputs
docs/design/explorations/staging-r1/README.md; T-132 task file and #161 review notes; Decision 081.

## Handoff notes
- **Gate PR #234** adds the `hero-results` flow (rows 1–5, "Also worth a look", sidebar, Show all cars link; `budget=40000` because 25000 has no `hero-more` on release 4) and the `hero-results-edit` flow (a change button opens its question). Verify: 2/2.
- **Phone sheet** (`src/components/HeroSheet.tsx`). It uses one DOM for the sidebar and the sheet, like the catalogue filters. Below 640 px (`max-sm`) the sidebar is hidden, and the phone bar `hero-phone-bar` shows the profile, the budget and "Answers & refine · n" (`hero-refine-open`). The sheet keeps focus inside. It closes with the ✕, "Show my top 10", Escape (unless a popover inside already handled it), a tap outside, a swipe down of more than 80 px on the top bar, or widening to 640 px or more. Opening pushes a history entry, and every close goes through `history.back()`. `Hero`'s popstate handler sees the open sheet and writes the current answers back into the entry it lands on, so refine changes made in the sheet survive Back. A change button inside the sheet closes it and pushes its question as usual. The answers list (`hero-answers`) now shows in the sheet too (`hidden max-sm:block lg:block`).
- **Row photos.** `src/lib/photos.ts` turns `generations[].image` into `/photos/<file>` only when every width is on disk in `<release>/images/`, so there is never a broken image. `src/app/photos/[file]/route.ts` serves those files (name regex, `immutable` cache, 404 for anything else). `CarThumb` and `PhotoCredit` live in `src/components/CarPhoto.tsx`: a fixed 72×48 box with `object-fit: cover`, lazy loading, alt "<make> <model> <generation>", and a credit ⓘ (the credit line plus a link to the file page) on the corner. On narrow rows the photo sits above the name; rows without a photo keep their old layout. The landing passes only `{src, credit, pageUrl}` per generation (119 on release 4). The shortlist rows got photos; the "Also worth a look" line rows didn't (they're already tight at 360 px).
- **Production (🟡).** The web image (`apps/web/Dockerfile` `catalogue` stage) copies only `catalogue.json`, so staging shows no photos until WS4 copies `images/` too. Staging also lacks `shortlist_scores.json` / `used_prices.json` today; see the WS0 INBOX line of 2026-11-27 23:05 UTC. Nothing breaks meanwhile.
- **Rule 5 note for WS0:** `src/lib/photos.ts` reads `<release>/images/` next to `catalogue.json`, through `latestCataloguePath()` from `catalogue.ts`. That is a second reader of release files, and `apps/web/AGENTS.md` (a gate file) should name it.

## Review
