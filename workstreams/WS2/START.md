# WS2 lane brief: web app

For any batch chat whose prompt touches this lane. Owner: WS0 (the coordinator). How chats work: [docs/process/README.md](../../docs/process/README.md) §3; rules: [rules.md](../../docs/process/rules.md). The lane builds the Next.js app: hero shortlist, catalogue (/cars, Explore), model / generation / variant pages, compare, /learn, open data page. English only at launch (Decision 082); simple by default, nerdy on demand.

## Start
1. Attach the repo with push access (`add_repo zkMenno/EV-Shortlist`, access `push`); add your row to `CHATS.md`.
2. Read `AGENTS.md`, `REVIEW.md` (from `origin/main`), `docs/process/README.md`, `apps/web/AGENTS.md`, your task files, this brief. UI work: also `docs/design/brand-design-decisions.md` and `docs/design/` (start at `SOURCE.md`).
3. Before each task and again before its first push: check open PRs and `git ls-remote --heads origin | grep <task-id>`; stop if another chat has it (G-41). Two WS2 chats built T-097 and T-130 twice that way.
4. Spec only where the task points: `docs/spec/master-spec-v2.md` §3–4 and §9–11, `launch-scope.md` (only Launch tasks, Decision 051).

## What the lane owns
`apps/web/` (except `apps/web/Dockerfile`, WS4). The app reads the published release (`data/releases/<latest>/`, Decision 008), glossary and copy from `data/taxonomy/` and `content/` (WS3), country config from `config/countries/` and `config/popularity.yaml` (WS3). Need a release field: WS1; copy or a glossary term: WS3 (meanwhile show the plain label, never crash on a missing term); schema: WS0. All such requests: one line in `workstreams/WS0/INBOX.md`. `apps/web/AGENTS.md` is a gate file: doc changes there go in their own PR. Decision numbers: ask WS0.

## Lane rules
- Strict TypeScript, server components by default, Vitest + Playwright, pnpm (Decision 007). Ariakit for complex widgets (Decision 056); the JS budget stays.
- Instant before clever: Explore loads fast, works without sign-up. Filters, compare tray and display level live in the URL; the compare tray never resets.
- Plain label first, technical term underneath, ⓘ tooltip from `glossary_terms`. Simple / Detailed / Nerd; Nerd shows source, date, licence, confidence, fallback rung (REVIEW D7).
- Metric units and euros; English only while `languages: []` in country config (other strings stay in the repo); no hard-coded brand name (config).
- Show uncertainty: estimates labelled, ranges say "about", DC charging never peak kW alone.
- Privacy: cookie-less analytics only. Trip fit (parked): addresses stay in the browser, coordinates rounded ~200 m, no route logging.
- Link-outs in a new tab with `rel="noopener"`, text links only, no third-party logos without permission.
- Parked features (Decision 051) stay behind flags, off: charging link-outs, Trip fit, bidi bits, known issues, registration charts, rankings.
- Don't change hero scoring (`src/lib/shortlist.ts`, Decision 065): the back-test runs the ranking visitors see.

## Verify before every push
- `pnpm --filter ./apps/web run lint`, `typecheck`, `test`, `build`; e2e for touched flows.
- The `verify` skill (`apps/web/.claude/skills/verify/SKILL.md`, `node scripts/verify.mjs --changed --base origin/main`): flows from `e2e/feature-map.yaml`, screenshots 360 + 1280 px, light + dark. Evidence pack in the PR body; commits end with `Verified: <how>`.
- Every 360 px check also once with letters ~6 % wider (G-44): CI fonts are wider than local ones. Re-run after every layout tweak, even a nit.

## Gotchas
- Merging main can bring apps/web changes the reviewer never saw: `git diff --stat HEAD~1 HEAD -- apps/web` before writing the merge message.
- Run `pnpm vitest run` again after editing `e2e/feature-map.yaml` (verify-map.test pins flow ids; triggers must resolve inside apps/web).
- A native `<select>` is as wide as its longest option. Next page files may only export page things: helpers go to `src/lib/`. Server components can't call functions from a `"use client"` file.
- A `useEffect` that depends on a callback prop re-runs every render: keep callbacks in a ref. `<details open={cond}>` snaps shut when `cond` turns false.
- Country names in sentences need per-country keys (prepositions); `Intl.NumberFormat` compact in de-DE doesn't shorten thousands (round first).
- Don't rename files during `pnpm build`. num-labels.test.ts can fail locally and pass in CI: check CI before calling something "red on main".
- Languages come only from `config/countries/<cc>.yaml` (`languages: []`, `default_language: en`); e2e that need a second language skip on `ENGLISH_ONLY` (`e2e/langs.ts`).

## Done (per task)
Acceptance criteria ticked · unit tests + a Playwright check for key flows · works at 360 px (also with wider letters) · all strings in the English dictionary · lint, types, tests, build green locally, then CI green on the PR head · PR template with evidence · Status + Handoff notes in the task file · fresh review before merge.

## Finish the batch
State lives in task files and PRs, not here. When the batch is done or blocked: one line in `workstreams/WS0/INBOX.md` (`- YYYY-MM-DD HH:MM UTC · from <chat link> · …`, with the four retro answers or a link to them), then stop. No STATUS or HANDOFF files.

## Open lane threads (from the retired WS2 HANDOFF, 2026-11-18; WS0 turns them into tasks)
- #126 (T-130 part 2) and then #137 (gate-only apps/web/AGENTS.md line + #118 redirect should-fix) wait for merge; merge main into #137 first if it conflicts.
- T-132 hero redesign (6th-chat line, branch `t-132-hero-questions`): plan in tasks/T-132; spec `docs/design/explorations/staging-r1/README.md` §T-132; suggested split questions / results.
- T-131 Popular used EVs (`data/editorial/popular_used.yaml`; landing page only, not Hero.tsx). T-135 photo cards on `GenerationCard` (`generations[].image`, credit under every photo; fetch-release must pull `images/*`).
- Verify flow `tooltip` takes the first of ~336 hidden nodes (`scripts/verify.mjs` ~223, `.first()`): match `:visible` or scope to the clicked term; small PR with a `Test-change:` line.
- #126 should-fix: used-price Nerd line lacks a licence until WS1 adds `licence` to used_prices.json band sources.
- #126 follow-ups: phone toggles above the list (first card at y≈760 at 360×800); used band reads p25–p75 under "Up to €25,000" (label "typical"?).
- From the Ariakit chat: brand fonts not loaded (Atkinson Hyperlegible, Bitter; body is system-ui); hero refine form not on the evs-field spec (17 px bold label, 48 px input).
