# WS0 handoff (2026-11-26 19:45 UTC, Antigravity: WS0 coordinator 2026-11-26)

Migrated from Claude to Antigravity on 2026-11-26 (**PR #208**, Decision 089, rule G-64). Pause procedure stays G-58 (HANDOFF + INBOX line + open task Status).

Repo: **zkMenno/EV-Shortlist** (Antigravity local clone + `gh` CLI; GraphQL, native CI triggers, and merged branch deletion all work normally — see `GEMINI.md`).

## How we work
One named coordinator conversation (`WS0 coordinator`, started with `/start-coordinator`). Every other conversation is a throwaway batch (`/start-batch`: one task or small batch, merges included when briefed, independent `/fresh-review` before merge, `sh scripts/merge_ready.sh <pr>` READY as its own step right before merge). Menno: one screen, plain language, 🟢/🟡/🔴, exact paste text in code blocks. The coordinator may merge its own docs / gate PRs after a fresh PASS.

## State
- Data release 3 is live (`data-v3`); **release 4 not built yet**. Its approvals: #177, #184, #189, #190, #194, #196, #198, #203 (+ any from T-162–T-164).
- Decisions up to **089**; next free **090** (from spare block `090–099`, WS0 block `080–089` is full). Tasks up to **T-165**; next free **T-166**. Rules up to **G-64**; next free **G-65**.
- Done: T-149–T-156, T-158, **T-159** (#198/#199/#203/#204, marked done in #209), T-160, T-161 (claim item → T-163), CI minutes (#207), Antigravity migration (#208), BOARD refresh (#209). Schema has `PublishedVariant.dc_speed_is_claim` (#205).
- Open PRs: **none**. Unhandled INBOX items: **none** (T-159 2026-11-19 17:40 UTC processed).

## Next batch conversations (briefs given to Menno 2026-11-26)
1. **Catalogue (WS3): T-162** — re-cite MX-30 + EV6 63, Elroq 85 DC check, Model X gen1, Citigo e / Mii, EV9, Marvel R, Sealion 7. (May run in parallel with T-163 / T-165.)
2. **Data (WS1): T-163** — TGK variant codes as split evidence (Model S 75R/75D, Model X 60X–100X), cited power / gross reach the release, `dc_speed_is_claim` + open data. (**Unblocked** now that T-159 is merged.)
3. **Data tools (WS1 + cross-lane): T-165** — G-61 seed-pinned tests + `seed` marker, G-62 missing-input flag report, G-63 `merge_ready` stuck checks, CI approvals (gate files in their own PR).
- After T-163 merges: **T-164** (WS3: cite power for remaining flag-less rows from T-161).
- After T-162–T-165 merge: build and publish **release 4**, then **T-157** (WS2: popularity from release 4, `images.tar` unpack, DC claim badge), then T-146 row thumbnails.

## Parked / later
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
- Merged branch `fix/agents-t141-ariakit` (#125) was deleted by WS0 on 2026-11-26. Unmerged/superseded branch `t-136-extra-models-2nd-chat` (absorbed into #129/#146) is still on origin if you want to delete it or confirm WS0 may delete it.
- 6 open questions in `QUESTIONS.md` (Q-003, Q-028, Q-037, Q-047, Q-072, Q-079) + T-041 phone tap check when convenient.

## Runs on its own when idle
GitHub Actions only: weekly data refresh (Mondays 03:17 UTC) opens or updates a data release PR; Dependabot patch / minor PRs merge themselves when green. Data PRs wait for a batch conversation to review and merge them.
