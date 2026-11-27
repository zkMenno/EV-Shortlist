# COORDINATOR handoff (2026-11-27 02:51 UTC, Antigravity: COORDINATOR 2026-11-26)

Migrated from Claude to Antigravity on 2026-11-26 (**PR #208**, Decision 089, rule G-64). Naming: Menno retired the `WS0` label — always write **COORDINATOR** (capitalized) in chat titles, prompts, and updates (repo paths `workstreams/WS0/HANDOFF.md` and `workstreams/WS0/INBOX.md` stay unchanged on disk so scripts/links don't break). Pause procedure stays G-58 (HANDOFF + INBOX line + open task Status).

Repo: **zkMenno/EV-Shortlist** (Antigravity local clone + `gh` CLI; GraphQL, native CI triggers, and merged branch deletion all work normally — see `GEMINI.md`).

## How we work
One named **COORDINATOR** conversation (started with `/start-coordinator`, retired via `/handoff` when context grows). Every other conversation is a throwaway builder batch (`/start-batch`: one task or small batch, merges included when briefed, independent fresh review via a separate subagent before merge, `sh scripts/merge_ready.sh <pr>` READY as its own step right before merge). Menno: one screen, plain language, 🟢/🟡/🔴, exact paste text in code blocks. The COORDINATOR may merge its own docs / gate PRs after a fresh PASS.

## State
- Data release 3 is live (`data-v3`); **release 4 is ready to build & publish (T-167)**. Its approvals in `config/approved_changes.yaml` (21 `release: 4` entries): #177, #184, #189, #190, #194, #196, #198, #203, #212, #213, #218, #219 (+ any gate approval T-167 needs for the 62 pre-existing RDW staging drift lines on `mg-mg4-gen1-xpower` and `skoda-enyaq-gen1-80x`).
- Decisions up to **089**; next free **090** (from spare block `090–099`, WS0 block `080–089` is full). Tasks up to **T-167**; next free **T-168**. Rules up to **G-68**; next free **G-69**.
- Done: T-149–T-156, T-158–T-166 (incl. **T-164** #218/#220 and **T-166** #219/#221), CI minutes (#207), Antigravity migration (#208), BOARD refreshes (#209, #217, #223), gate rules G-65–G-68 (#216, #222). Schema has `PublishedVariant.dc_speed_is_claim` (#205).
- Open PRs: **none**. Unhandled INBOX items: **none**.

## Next batch conversations (brief given to Menno 2026-11-27)
1. **Data release 4 (WS1): T-167** (`tasks/T-167-data-release-4.md`) — trace/approve the 62 pre-existing RDW staging drift lines (`mg-mg4-gen1-xpower` [61], `skoda-enyaq-gen1-80x` [1]), refresh staging, build release 4 (`images.tar`, `generations[].popularity`, `dc_speed_is_claim`, 128+ `maker-docs` facts, 419 variants), upload `data-v4` via `GITHUB_REPOSITORY=zkMenno/EV-Shortlist pipeline/scripts/gh-publish-release.sh data/releases/4`, open & merge `Data release 4` PR (`latest = 4`), confirm `Data publish` + `Images` staging deploy green on `main`.
2. **Next after T-167 lands — Web (WS2): T-157** (`tasks/T-157-web-popularity-from-release.md`) — web reads `generations[].popularity` from release 4, unpacks `images.tar`, displays DC claim badge for `dc_speed_is_claim`. Then **T-146** (row thumbnails) and **QA** fresh launch review on release 4 + staging.

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
