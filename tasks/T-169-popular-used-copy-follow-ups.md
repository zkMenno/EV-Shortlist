# T-169 Popular used EVs + photo credits: wording and accessibility follow-ups
Role: builder   Lane: WS2 (apps/web) + WS3 (data/editorial `why` lines, content/)   Wave: launch (before public launch; not blocking staging)
Status: todo

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

## Review
