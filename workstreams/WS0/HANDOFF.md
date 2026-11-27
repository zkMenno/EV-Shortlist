# COORDINATOR handoff (2026-11-27 22:20 UTC, Claude: COORDINATOR 2026-11-27 evening, https://claude.ai/code/session_01JuyZEWwQDPkqpriznYQTsU)

Note 2026-11-27 22:20: Menno opened this COORDINATOR in Claude again (after building in Antigravity). Both hosts work: Claude uses CLAUDE.md + the Claude-era mechanics (no GraphQL, `workflow_dispatch` after push, PRs via `gh api`); Antigravity uses GEMINI.md.

Migrated from Claude to Antigravity on 2026-11-26 (**PR #208**, Decision 089, rule G-64). Naming: Menno retired the `WS0` label — always write **COORDINATOR** (capitalized) in chat titles, prompts, and updates (repo paths `workstreams/WS0/HANDOFF.md` and `workstreams/WS0/INBOX.md` stay unchanged on disk so scripts/links don't break). Pause procedure stays G-58 (HANDOFF + INBOX line + open task Status).

Repo: **zkMenno/EV-Shortlist** (Antigravity local clone + `gh` CLI; GraphQL, native CI triggers, and merged branch deletion all work normally — see `GEMINI.md`; release fetches use `ev release fetch latest --via-gh` [G-66], release publishes use `gh workflow run data-refresh.yml` [G-70]).

## How we work
One named **COORDINATOR** conversation (started with `/start-coordinator`, retired via `/handoff` when context grows). Every other conversation is a throwaway builder batch (`/start-batch`: one task or small batch, merges included when briefed, independent fresh review via a separate subagent before merge, `sh scripts/merge_ready.sh <pr>` READY as its own step right before merge). Menno: one screen, plain language, 🟢/🟡/🔴, exact paste text in code blocks. The COORDINATOR may merge its own docs / gate PRs after a fresh PASS.

## State
- **Data release 4 (`data-v4`, `latest = 4`) is LIVE** on `main` (`49e0a59`) and `https://staging.evshortlist.com/health` (`{"status":"ok","release":4}`): `419` variants, `70,176` facts, `0` provenance/licence/impossible-value problems, `images.tar` (`29.3 MB`, `357` WebP files / `119` photos), `156` generations with `generations[].popularity` (Spearman `0.952`), `4` rows with `dc_speed_is_claim: true`, `150` `maker-docs` + `174` `manual` facts, client catalogue `170.6 KB` gzip (#227).
- **`gate-guard` is now in `enforce` mode** and protects `GEMINI.md` + `.agents/**` (**Decision 090**, #230 + #231).
- Decisions up to **090**; next free **091** (from spare block `091–099`). Tasks up to **T-167**; next free **T-168**. Rules up to **G-70**; next free **G-71**.
- Done: T-149–T-156, T-158–T-167 (data release 4 live: #224/#225/#226/#227), CI minutes (#207), Antigravity migration (#208), BOARD refreshes (#209, #217, #223, #229), gate rules G-65–G-70 (#216, #222, #228), coordinator docs tidy + Decision 090 (#230), gate-guard enforce + gate docs tidy (#231). Schema has `PublishedVariant.dc_speed_is_claim` (#205).
- **T-157 done** (#232 → `f833b3d`, 2026-11-27 12:37 UTC). Open PRs: **none** (checked 22:15 UTC). Unhandled INBOX items: **none**. Staging health 22:16 UTC: `{"status":"ok","release":4}`. Running builder batch: **none**; next = overnight WS2 batch T-146 → T-135 → T-131 (WS2).

## Next batch conversations
1. ~~**Web (WS2): T-157**~~ done #232. (`tasks/T-157-web-popularity-from-release.md`) — `apps/web/scripts/popularity.mjs` reads `generations[].popularity` from release 4 (Spearman ≥ 0.95, D5 N-1 fallback); `apps/web/scripts/fetch-release.mjs` unpacks `images.tar` + verifies sha256 per file (releases 1–3 still work); `dc_speed_is_claim: true` claim badge carried in `explore-data.ts` + shown on all 4 DC speed fields; `apps/web/scripts/budget.mjs` 85 % (`255 KB`) early warning (G-69).
2. **Next after T-157 lands — Web (WS2): T-146** (`tasks/T-146-hero-results-follow-ups.md`) — phone Refine bottom sheet (≤ 640 px), row photo thumbnails from unpacked `images.tar` (Decision 081), `hero-results` feature-map flow (gate PR approved by COORDINATOR in advance). Followed by **T-135** (photo cards) and **T-131** (WS2 Popular used EVs landing section).
3. **After T-157 + T-146 (+ T-135/T-131):** Fresh **QA** launch review on release 4 + staging before public launch.

## Parked / later
- Post-release-4 catalogue/pipeline follow-ups from T-167: (a) WS3: 10 report-only G-62 `missing_input_flag_changes` vs pre-Decision-088 rel 3 (7 missing sibling `power_kw` on `audi-e-tron-ge-55`, `mercedes-eqa-h243-300-350-4matic`, `kia-ev6-gen1-gt`; 3 missing `dc_km_per_20min` incl. T-111 withheld Raven LR); (b) WS1 optional: small-volume RDW trims like MG4 XPower (`n=2 < MIN_SAMPLE=5` in `___7%` sample) cross-joining `rdw-tgk` codes for power/WLTP evidence on `narrow_full` price records.
- Remaining `no-variant` catalogue groups after T-162 (top by NL cars): `kia-ev5-gen1` (4,665), `bmw-ix3-gen2` (3,368), `mg-mg5-gen1` (2,960), `opel-ampera-e-gen1` (2,622), `kia-ev4-gen1` (2,307), `opel-frontera-gen1` (2,027), `xpeng-g9-gen1` (1,822).
- T-159 follow-ups: Q8 e-tron rows hold each other's codes (`tgk_split`); EV6 gen1 77 kWh ties; Taycan 2020–21 versions out on year + no rows for 2024 Taycan / Taycan 4 / GTS (WS3); older shipped WLTPs causing T-155 holds (ID.4 Pro 496 vs 575–650; Enyaq 85 752 vs 607–633).
- OpenEV `markets` filter: parked (zero-diff allowlist design in INBOX 2026-11-18 19:14).
- T-142 data pipeline hardening (report first).
- PR-body checker recounting "main has N" claims (T-155 retro): parked.
- T-158 optional: the stale-lock takeover race (#185 nit 3).
- WS4 follow-up from #207: `.github/workflows/images.yml` ignores `docs/**`, but the web image reads `docs/design/**` (token/font changes don't rebuild staging).

## Coordinator remaining items
- Refresh `BOARD.md` (include #230/#231 + Decision 090 enforce) alongside the next T-157 board update so `main` stays quiet while T-157 finishes.
- **T-128** (`Verified:` commit-stamp warning in CI `repo-checks` + flaky-test / self-merge prose in `AGENTS.md`).
- Tiny non-blocking nits from #231 review: clarify `rules.md` G-38 parenthetical (i18n.test.ts still runs all-six completeness tests) and `infra/AGENTS.md` rule 2 old "real domain until decided" line on next gate edit.

## Menno by hand
- Merged branch `fix/agents-t141-ariakit` (#125) was deleted by COORDINATOR on 2026-11-26. Superseded branch `t-136-extra-models-2nd-chat` (absorbed into #129/#146) is still on origin if you want to delete it or confirm COORDINATOR may delete it.
- 6 open questions in `QUESTIONS.md` (Q-003, Q-028, Q-037, Q-047, Q-072, Q-079) + T-041 phone tap check when convenient.

## Runs on its own when idle
GitHub Actions only: weekly data refresh (Mondays 03:17 UTC) opens or updates a data release PR; Dependabot patch / minor PRs merge themselves when green. Data PRs wait for a batch conversation to review and merge them.
