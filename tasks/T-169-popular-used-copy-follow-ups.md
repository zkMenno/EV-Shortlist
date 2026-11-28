# T-169 Popular used EVs + photo credits: wording and accessibility follow-ups
Role: builder   Lane: WS2 (apps/web) + WS3 (data/editorial `why` lines, content/)   Wave: launch (before public launch; not blocking staging)
Status: review (batch: staging fix + web follow-ups, https://claude.ai/code/session_01JuyZEXh24GFZTn2JpiC2bs, 2026-11-28)

## Goal
Clean up the review nits from #236 / #237 so the landing section and photo credits read right.

## Acceptance criteria
- [ ] "How we pick these" points to an explanation of this list's points method, not `/cars#how-we-rank` (the catalogue sort) (`apps/web/src/app/.../page.tsx:143`).
- [ ] "the owner" never reads as the car's previous owner: say "the site owner's" (or equivalent) in `landing.popular.*` strings and the WS3 `why` lines.
- [ ] Years don't show twice when the generation name already holds them (`PopularUsed.tsx:83`).
- [ ] `generationTitle` no longer gives "Kia Niro EV e-Niro (Gen 1, DE)"; add a unit test with that case.
- [ ] Landing "#N most registered" (model rank) and catalogue "#N popular" (generation rank) are labelled so a visitor can tell them apart.
- [ ] Credit links say "opens in a new tab" to screen readers; CC BY deed link present.
- [ ] Optional if small: used price bands show source + date in Nerd mode (pre-existing, Explore too); otherwise note it for the QA review.
- [ ] 360/1280 px light + dark (+ ~6 % wider letters, G-44), axe clean, fresh review, `Verified:` on every commit.

## Inputs
INBOX 2026-11-28 09:15 (WS2 overnight follow-ups 1–7); #236 and #237 review comments.

## Out of scope
Hero scoring (`src/lib/shortlist.ts`, Decision 065); new sections.

## Handoff notes
- (1) "How we pick these" is now a `<details>` in the section (`popular-how`, `#how-we-pick`) explaining this list's points. Numbers come from `method` in `data/editorial/popular_used.yaml` → `scripts/popular-used.mjs` → `popular-used.generated.json` (new `registration_top: 40` in `build_popular_used.py` METHOD, now also used for the points formula). No more link to `/cars#how-we-rank`.
- (2) "the site owner" in the WS3 `why` lines (re-generated, same order) and in `landing.popular.intro`, `sort.popular.why`, `catalogue.how.picks`, `card.popular.nerd` (EN + NL). `hero.caveat.owner` / `owner.*` ("one owner's picks", "Owner's note") left as they are: they say "one owner", not "the owner".
- (3) Years once: the card skips "· years" when the generation name holds a year (`Model 3 (2019-2023)`).
- (4) `generationTitle`: "Niro EV" + "e-Niro (Gen 1, DE)" → "Kia e-Niro (Gen 1, DE)"; only that title changes across release 4 (checked all 260 make/model/generation triples). Unit test `src/lib/generation-title.test.ts`.
- (5) Catalogue tag "#{n} popular" → "#{n} in Most popular" (NL "#{n} in Meest populair"); landing lines already say "most registered EV model". e2e expectations updated (Test-change).
- (6) Credit links: sr-only "(opens in a new tab)" on file-page links (caption + ⓘ), plus a "Licence terms" link to the CC deed (`src/lib/licence-url.ts`, SPDX id → deed; none for public domain). One `photoText(t, term)` helper replaces four copies of the strings; landing + catalogue pass `licence` in the photo refs. New keys `photo.licence`, `photo.newTab`, `landing.popular.method.*` in all six languages.
- Optional (7) used price source + date in Nerd mode: not done (pre-existing, Explore too); for the QA review.
- Evidence: vitest 64 files / 532 tests; Playwright popular-used, catalogue, photos, hero, smoke, a11y: 111 pass (1 photos test updated for the second caption link, then 6/6); screenshots 360 + 1280, light + dark (+6 % letters at 360): no overflow.

## Review
