# T-135 Photos on cards and pages with a credit line
Role: builder   Lane: WS2: apps/web/   Wave: launch (staging feedback 2026-11-17)
Status: review (WS2 overnight batch, 2026-11-28; builds on T-146 #235)

## Goal
Cards and generation pages show the car's photo with its credit.

## Acceptance criteria
- [x] Card and generation page show the photo from the release (responsive sizes, lazy load, alt text = make model generation)
- [x] Credit line under every photo (author, licence, link); a neutral placeholder when there is no photo
- [x] No layout shift (fixed aspect ratio); axe clean; 360/1280 px screenshots
- [x] Verify skill for the lane; evidence pack in the PR; `Verified:` on every commit
- [ ] Fresh review (REVIEW.md from origin/main) passes

## Inputs
Decision 081; T-134

## Out of scope
Anything not on docs/spec/launch-scope.md.

## Handoff notes
- **Shared parts come from T-146 (#235):**
  - `src/lib/photos.ts` (`generationPhoto` / `generationPhotos`) shows a photo only when every width is on disk in `<release>/images/`.
  - The `/photos/<file>` route serves them from our origin.
  - `src/components/CarPhoto.tsx` holds `CarThumb` and `PhotoCredit`.
- **New: `CarFigure`** in `CarPhoto.tsx`.
  - It is a fixed-ratio box with `object-fit: cover`: 3:2 on pages and 16:9 on cards (`card`), so a phone shows more of the list.
  - `srcset` covers 400/800/1600 with `sizes` per use. Cards load lazily; the generation page loads `eager`.
  - Alt text is "<make> <model> <generation>"; on the generation page it is the h1.
  - The `figcaption` reads "Photo: <credit>" (author, licence, "via Wikimedia Commons") and links to the file page (new tab, `noopener nofollow`).
  - Without a photo it shows the same-size dashed placeholder, "No photo yet", with a car outline icon.
  - Classes: `.evs-photo*` in `globals.css`. Colours come from tokens only.
- **Catalogue cards:** `/cars` passes `photos` (src, srcset, credit, file page) to `Explore`, and `GenerationCard` renders `CarFigure` at the top. Release 4 has 100 of 161 generations with a photo on `/nl/en/cars`.
- **Generation page:** the photo sits under the years line (`gen-photo` / `gen-photo-none`).
- **Tests:** `e2e/photos.spec.ts` covers the card src/srcset/lazy/alt/credit link, the 16:9 box, a placeholder card and its generation page, the eager main photo, and axe in light and dark.
- **Production (🟡):** this has the same dependency as T-146. The web image must carry `<release>/images/` (WS0 INBOX 2026-11-27 23:05 UTC). Until then staging shows placeholders, never broken images.
- **Licence nit (from the #235 review):** CC BY 2.0/3.0 credits could also link the licence deed. Logged for WS0/WS3; not changed here.

## Review
<!-- Reviewer: name, date, head SHA, REVIEW.md items + verdicts. -->
