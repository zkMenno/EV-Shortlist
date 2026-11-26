# Board

One screen: what's happening. Coordinator only. Task details live in `tasks/`.

_Last updated: 2026-11-26 23:07 UTC by COORDINATOR (T-165 + T-162 done, T-163 #215 open, T-166 added)._

## Launch scope (Decision 051, docs/spec/launch-scope.md)

Builders take only tasks in **Launch**. Everything else needs Menno's yes. Built work for parked features stays behind feature flags (off).

**Launch, staging feedback (Menno, 17 Nov; docs/spec/feedback-2026-11-17-staging.md):** T-130 catalogue page + popularity sort (WS2 + UX) · T-131 Popular used EVs (WS3 + WS2) · T-132 hero questions redesign (UX → WS2) · T-133 photo sourcing + licence log (WS3) · T-134 image fields (WS1) · T-135 photo cards (WS2) · T-136 catalogue coverage report, report before build (WS1 + WS3) · T-137 English only (WS2). Decisions 081, 082. **Parked until after launch:** translations (T-117/T-119 follow-ups).

**Launch fixes from QA A-35 (blockers, do first):** T-110 Model Y + seed figures (WS3) · T-111 plausibility + licence gates (WS1) · T-112 new list prices (WS3) · T-113 depreciation estimate (WS1) · T-114 hero reads release scores (WS2) · T-115 budget rule (WS2) · T-116 release 2 (WS1, after T-110–T-113) · T-117 DE/FR/ES/IT strings (WS2 + WS3) · T-118 Spain + Italy data (WS3 + WS1) · T-119 /es/es + /it/it (WS2). Decisions 064–066.

**Launch, hero:** T-080 hero shortlist (WS2) · T-067 profile picker + suggested sort (WS2) · T-066 schema shortlist rules (WS0) · T-069 shortlist scores in the release (WS1) · T-068 seed gaps for picks (WS3) · T-081 used price by build year (WS1 + WS3) · T-056 free price indices (WS1) · T-043 loan estimate only (WS2/WS3)
**Launch, catalogue:** T-010 compare · T-045 differences only · T-050 country + language URLs · T-012 i18n · T-051 / T-052 seed coverage · T-041 listing templates · T-062 / T-063 data fixes · T-065 schema follow-ups
**Launch, data:** T-064 releases out of git · T-034 climate · T-032 / T-033 consumption model (winter range) · T-035 back-test · T-031 heat pump seed · open data download (built, Decision 016)
**Launch, content:** T-039 winter range · T-027 charging in 2026 · T-082 batteries + battery health · glossary tooltips
**Launch, infra:** T-040 AppInfra staging · T-013 deploy · T-064 storage part

**Process: verification layer (Decision 062):** Launch: T-120 REVIEW.md (WS0) · T-121 gate-guard (WS0, observe → enforce after review) · T-122 rule register (WS0) · T-123 release-diff test (WS1) · T-126 verify skill web (WS2) · T-127 verify skill pipeline (WS1) · T-128 Verified stamp + flaky policy + self-merge rule (WS0). Not launch-blocking: T-124 property tests pipeline (WS1) · T-125 property tests web (WS2) · T-129 reviewer eval set (parked, after launch).

**After launch (parked):** T-011 rankings pages · T-019 / T-020 / T-021 / T-022 bidirectional · T-024 / T-025 / T-026 / T-028 charging pages + link-outs (built parts stay flagged off) · T-029 ABRP deep links · T-036 quick range check (absorbed into T-080) · T-037 / T-038 Trip fit routes · T-042 bidi verification · T-044 / T-046–T-049 variant clues + finder · T-053 / T-058 registration history display · T-061 known issues · lease figures (rest of T-043)

## Launch, catalogue + data (COORDINATOR, 2026-11-26)
Done: T-149–T-156, T-158, T-159 (#198/#199/#203/#204), T-160, T-161 (claim item → T-163), T-162 (#212/#214), T-165 (#210/#211). Open: T-163 TGK variant codes + cited values publish + DC claim flag (WS1, gate #213 merged, #215 open) · T-164 cite power, flag-less rows (WS3, after T-163 merges) · T-166 seed-marker scan G-65 + `ev release fetch --via-gh` G-66 + Kia EV9 GT split (WS1) · T-157 web popularity + photo bundle + DC claim badge (WS2, after release 4).

## Now
**Open PRs:**
- **#215** T-163 (WS1: TGK variant codes, cited power/gross publish, `dc_speed_is_claim`; gate #213 already merged)

**Live:** `staging.evshortlist.com` deploys from `main`; data release 3 (`data-v3`) is live; **release 4 not built yet**.

**Ready to launch next (in Antigravity, `/start-batch`):**
1. **Data tools & matching (WS1): T-166** — G-65 seed-marker scan test, G-66 `ev release fetch --via-gh`, Kia EV9 GT `tgk_split` split (from T-162/T-165 retros).
2. **Catalogue (WS3): T-164** — cite power for remaining flag-less rows from T-161 (starts as soon as **#215** T-163 merges).

## Next (launch scope only)
- **WS1:** Build and publish **data release 4** once T-163, T-164, and T-166 merge.
- **WS2:** **T-157** (web reads popularity from release 4, unpacks `images.tar`, shows DC claim badge), then T-146 row thumbnails.
- **COORDINATOR:** Doc tidy PR + gate PR (`gate-guard` observe → enforce, add `GEMINI.md`/`.agents/**` to `config/gate-files.yaml`, `infra/AGENTS.md` align with CI staging deploy); T-128 `Verified:` stamp.
- **WS4:** `images.yml` should not ignore `docs/design/**` (web image reads tokens/fonts from it).
- **QA:** Fresh launch review on release 4 + staging before public launch.

## Blocked on Menno
- 6 open questions in [QUESTIONS.md](QUESTIONS.md) (Q-008 answered via Decisions 068 / 087): Q-003 PRs on main · Q-028 listing URL patterns · Q-037 RDW wording · Q-047 KilowattApp curves · Q-072 CCD2 warning wording · Q-079 Actions opening data-release PRs
- T-041 listing templates: his tap check on a phone
- Real data in production waits for off-site backups (AppInfra #93). EV holds nothing to back up at launch; the trigger and the AppInfra handoff are in ROADMAP.md Phase 0, "Backups" (2026-11-17)

## Workstreams and file ownership

Chats talk through the coordinator's inbox, `workstreams/WS0/INBOX.md`, never through Menno (Decision 014, docs/process §2). Full table and rules: [docs/process/README.md](docs/process/README.md).

| Owner | Paths |
|---|---|
| COORDINATOR (`WS0`) | AGENTS.md, CLAUDE.md, GEMINI.md, .agents/, BOARD.md, QUESTIONS.md, DECISIONS.md, ROADMAP.md, CHANGELOG.md, docs/spec/, packages/schema/, tasks/, research/, audits/, workstreams/README.md + */START.md, .github/ (not image workflows) |
| WS1 pipeline | pipeline/ (not Dockerfile), data/sources.yaml, data/field_sources.yaml, data/SOURCES.md, data/releases/, data/review/ |
| WS2 web | apps/web/ (not Dockerfile) |
| WS3 curation | data/seed/, data/manual/, data/taxonomy/, content/, config/ |
| WS4 infra | infra/, pipeline/Dockerfile, apps/web/Dockerfile, .github/workflows/image*.yml |
| WS5 growth | docs/outreach/, docs/growth/, docs/brand/ |
| UX design | docs/design/ |
| QA reviewer | audits/, `## Review` sections in tasks/ |
| everyone | append-only lines in workstreams/WS0/INBOX.md (the one inbox); workstreams/WS0/HANDOFF.md is the coordinator's |

## Done
- 2026-11-26: T-162 (#212 gate, #214 data: re-cited MX-30 + EV6 63, fixed Elroq 85 DC 185 → 135 kW, seeded 17 cited rows incl. Model X gen1 / Citigo e / Mii / EV9 / Marvel R / Sealion 7); T-165 (#210 gate, #211 main: G-61 237 seed-marked tests in `data_qa.sh`, G-62 `ev verify` missing-input flags, G-63 `merge_ready` stuck checks, CI `ev release approvals`); Antigravity migration (#208, Decision 089, G-64) & BOARD refresh (#209)
- 2026-11-24: CI minutes cut (#207): note-only skip, single web build, pipeline release cache
- 2026-11-19: T-149–T-156, T-158, T-159 (#198/#199/#203/#204), T-160, T-161; schema `dc_speed_is_claim` (#205); rules G-48–G-63 (through #206); Decisions 086–088
- 2026-11-18: Data release 3 (`data-v3`), T-130, T-131 (WS3), T-132–T-134, T-136, T-137, T-140, T-141, T-143–T-145, T-148, Ariakit (Decision 056), people carriers (Decision 084), WLTP next to real range (Decision 085), one coordinator + batch chats (#122)
- 2026-11-17: staging.evshortlist.com live (#88/#89/#94); data release 2 (`data-v2`); verification layer live: REVIEW.md, gate-guard (observe), rule register G-01–G-33 (#42, #45); T-125 web property tests, T-126 web verify skill, hero a11y + phone fixes, T-096 compare labels (#47–#55); docs tidy + `_archive/` (Decision 063)
- 2026-11-17: batch merge of 10 waiting PRs (#39): T-069 shortlist scores, T-081/T-056 used price bands, T-091 parked flags, T-068 seed gaps, T-031 heat pump, T-041 templates, T-100 glossary, /learn pages (T-082, T-039, T-027), T-093, T-094, T-081 NL aggregates (#38)
- 2026-11-15: hero shortlist (T-080), suggested sort (T-067), differences only (T-045), open data page (T-090), schema for shortlist rules (T-066/T-065), climate (T-034), consumption model + back-test (T-032/T-033/T-035), charging stats (T-025), releases out of git part 1 (T-064)
- 2026-11-15: overnight prototype 1 (#1, waves 1–4 + T-053–T-061) and research pack (#2); spec mirrored to docs/spec; workstreams set up; GitHub repo, CI, templates, security settings
