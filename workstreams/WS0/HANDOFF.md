# COORDINATOR handoff (2026-11-26 23:33 UTC, Antigravity: COORDINATOR 2026-11-26)

Migrated from Claude to Antigravity on 2026-11-26 (**PR #208**, Decision 089, rule G-64). Naming: Menno retired the `WS0` label — always write **COORDINATOR** (capitalized) in chat titles, prompts, and updates (repo paths `workstreams/WS0/HANDOFF.md` and `workstreams/WS0/INBOX.md` stay unchanged on disk so scripts/links don't break). Pause procedure stays G-58 (HANDOFF + INBOX line + open task Status).

Repo: **zkMenno/EV-Shortlist** (Antigravity local clone + `gh` CLI; GraphQL, native CI triggers, and merged branch deletion all work normally — see `GEMINI.md`).

## How we work
One named **COORDINATOR** conversation (started with `/start-coordinator`). Every other conversation is a throwaway builder batch (`/start-batch`: one task or small batch, merges included when briefed, independent fresh review via a separate subagent before merge, `sh scripts/merge_ready.sh <pr>` READY as its own step right before merge). Menno: one screen, plain language, 🟢/🟡/🔴, exact paste text in code blocks. The COORDINATOR may merge its own docs / gate PRs after a fresh PASS.

## State
- Data release 3 is live (`data-v3`); **release 4 not built yet**. Its approvals: #177, #184, #189, #190, #194, #196, #198, #203, #212, #213 (+ any from T-164 / T-166).
- Decisions up to **089**; next free **090** (from spare block `090–099`, WS0 block `080–089` is full). Tasks up to **T-166**; next free **T-167**. Rules up to **G-67**; next free **G-68**.
- Done: T-149–T-156, T-158, T-159 (#198/#199/#203/#204), T-160, T-161, **T-162** (#212/#214), **T-163** (#213/#215), **T-165** (#210/#211), CI minutes (#207), Antigravity migration (#208), BOARD refreshes (#209, #217), gate rules G-65–G-67 (#216). Schema has `PublishedVariant.dc_speed_is_claim` (#205).
- Open PRs: **none**. Unhandled INBOX items: **none**.

## Next batch conversations (briefs ready for Menno 2026-11-26)
1. **Data tools & fixes (WS1): T-166** — G-65 automated seed-marker scan test, G-66 `ev release fetch --via-gh` fallback for proxy-routed VMs, Kia EV9 GT `tgk_split.yaml` split (`kia-ev9-gen1-gt` vs `kia-ev9-gen1-99kwh-awd`, following G-67), and Stellantis 100→115 kW `derive/shortlist.py:130` `trim_lines` IEEE-754 float boundary fix.
2. **Catalogue (WS3): T-164** — cite `power_kw` for the 20 remaining flag-less rows from T-161 + cite `ac_kw: 22` for `renault-twingo-gen3-22kwh` (**unblocked** now that T-163 merged; note `maker-docs.cited_hosts` for seed `cited:` blocks vs `manual.cited_hosts` for `data/manual/`).
- After T-164 and T-166 merge: build and publish **data release 4** (investigate/approve the pre-existing `mg-mg4-gen1-xpower` RDW 2024 NL price / `used_prices` and `skoda-enyaq-gen1-80x` 48.0→47.9 staging drift noted by T-163), then **T-157** (WS2: popularity from release 4, `images.tar` unpack, DC claim badge), then T-146 row thumbnails.

## Parked / later
- Remaining `no-variant` catalogue groups after T-162 (top by NL cars): `kia-ev5-gen1` (4,665), `bmw-ix3-gen2` (3,368), `mg-mg5-gen1` (2,960), `opel-ampera-e-gen1` (2,622), `kia-ev4-gen1` (2,307), `opel-frontera-gen1` (2,027), `xpeng-g9-gen1` (1,822).
- T-159 follow-ups (non-blocking for release 4): Q8 e-tron rows hold each other's codes (`tgk_split`); EV6 gen1 77 kWh ties; Taycan 2020–21 versions out on year + no rows for 2024 Taycan / Taycan 4 / GTS (WS3); older shipped WLTPs causing T-155 holds (ID.4 Pro 496 vs 575–650; Enyaq 85 752 vs 607–633).
- OpenEV `markets` filter: parked (zero-diff allowlist design in INBOX 2026-11-18 19:14).
- T-142 data pipeline hardening (report first), T-135 photo cards, T-131 WS2 landing section, and a QA review on release 4 + staging.
- PR-body checker recounting "main has N" claims (T-155 retro): parked.
- T-158 optional: the stale-lock takeover race (#185 nit 3).
- WS4 follow-up from #207: `.github/workflows/images.yml` ignores `docs/**`, but the web image reads `docs/design/**` (token/font changes don't rebuild staging).

## Coordinator doc / gate should-fixes (batch into one docs PR + one gate PR)
- **Docs PR:** R-30:85 wording; stale lines in lane START files; G-44 / G-41 and REVIEW D4 / D8 wording; G-38 "Enforced by" names parked T-117; `infra/README.md` old "apply by hand" wording; `QUESTIONS.md` still says "(7)" with answered Q-008 inline (6 open); `docs/design/brand-design-decisions.md` old `EV-Finder` links and `claude-only-links.md` note (#208 nit 2).
- **Gate PR:** `config/gate-files.yaml` observe → enforce + add `GEMINI.md` and `.agents/**` (#208 nit 4); `infra/AGENTS.md` rules 1–2 out of date since CI deploys staging; `rules.md` note for T-158's `docs/process/README.md` edit.

## Menno by hand
- Merged branch `fix/agents-t141-ariakit` (#125) was deleted by COORDINATOR on 2026-11-26. Superseded branch `t-136-extra-models-2nd-chat` (absorbed into #129/#146) is still on origin if you want to delete it or confirm COORDINATOR may delete it.
- 6 open questions in `QUESTIONS.md` (Q-003, Q-028, Q-037, Q-047, Q-072, Q-079) + T-041 phone tap check when convenient.

## Runs on its own when idle
GitHub Actions only: weekly data refresh (Mondays 03:17 UTC) opens or updates a data release PR; Dependabot patch / minor PRs merge themselves when green. Data PRs wait for a batch conversation to review and merge them.
