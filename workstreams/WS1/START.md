# WS1 lane brief: data pipeline

For any batch chat whose prompt touches this lane. Owner: WS0 (the coordinator). How chats work: [docs/process/README.md](../../docs/process/README.md) §3; rules: [rules.md](../../docs/process/rules.md). The lane turns open sources into versioned, traceable catalogue releases and computes our own numbers (real range, winter range, DC charging, consumption, used price bands, shortlist scores).

## Start
1. Attach the repo with push access (`add_repo zkMenno/EV-Shortlist`, access `push`); add your row to `CHATS.md`.
2. Read `AGENTS.md`, `REVIEW.md` (from `origin/main`), `docs/process/README.md`, `pipeline/AGENTS.md`, your task files, this brief.
3. Before each task and again before its first push: check open PRs and `git ls-remote --heads origin | grep <task-id>`; stop if another chat has it (G-41).
4. Spec only where the task points: `docs/spec/master-spec-v2.md` §5–8 and §12, `source-matrix.md`, `data-sources.md`, `charging-buildout.md`, `trip-fit.md` §5 and §7, `bidirectional-and-connectors.md`. Scope: `docs/spec/launch-scope.md` (only Launch tasks, Decision 051).

## What the lane owns
`pipeline/` (except `pipeline/Dockerfile`, WS4), `data/sources.yaml`, `data/field_sources.yaml`, `data/SOURCES.md`, `data/releases/`, `data/review/`. Not yours: `packages/schema` (WS0), `data/seed`, `data/manual`, `data/taxonomy`, `config/` (WS3), `apps/web` (WS2), `infra/` (WS4). Need a schema field or a change in another lane: one line in `workstreams/WS0/INBOX.md` with the exact fields, then work on something else. Decision numbers: block 040–049.

## Lane rules
- Every number is a Fact with source, retrieval date, confidence and licence. Estimates carry `estimate: true`. "Not disclosed" is a real value; uncertain → review queue (`data/review/`). Never invent data.
- Licence gate (Decision 009): no named licence or written permission → never in a public release. ODbL and CC BY-SA stay out of CC BY output. Charging infrastructure: aggregates only, never point-level.
- No raw data in git; fixtures only (`pipeline/tests/fixtures/<source>/`). Tests never call the network.
- Jobs run at night (00:30–02:30 UTC), low priority, inside 1 GB / 1 CPU (Decision 006). Big one-off imports on a temporary machine.
- Python 3.12, type hints, `ruff`, `pytest`, `uv` (Decision 007). Config and data tables over hard-coded logic: a new country, chemistry or source is a new row.
- Derived scores, bands and models: dry run on the latest release rows before tests, back-test section in qa.json (G-10). A derived field that reuses an official field's name sits on the same basis; back-test it against official values where both exist.
- A new QA threshold PR quotes its hit list on the latest release (count + names).
- Matching or merge-logic change: same-data rebuild diff in the PR body (G-43, REVIEW D4) and the 5 tricky cars (EV6, Ioniq 5, MG4, Model Y LR vs Juniper, P7+).

## Verify before every push
- `cd pipeline && uv run ruff check . && uv run ruff format --check . && uv run pytest` (fetch release assets first: `uv run ev release fetch latest`, or `uv run ev release fetch latest --via-gh` in proxy-routed Antigravity VMs where HTTP downloads hit SSRF checks — rule G-66).
- Data changes: the `verify-pipeline` skill (`pipeline/.claude/skills/verify/SKILL.md`, `uv run ev verify`): rebuild from staging, release diff vs N-1 (approvals in `config/approved_changes.yaml`, its own gate PR), back-tests, tricky cars. Evidence pack in the PR body; commits end with `Verified: <how>`.
- Changed `data/sources.yaml`: run `node apps/web/scripts/sources.mjs` and `git diff --exit-code` (the web copy must be regenerated, or CI `web` fails).

## Gotchas
- Same-data rebuild recipe (from #135): detached worktree of `origin/main`, copy release assets in, `uv run ev refresh --force --no-release` (all 16 sources, ~20 min, peak ~450 MB), then `build_release(data_dir)` with old and new code; diff rows and facts.
- `gh pr create` fails in these sessions (GraphQL blocked): use `gh api repos/zkMenno/EV-Shortlist/pulls`.
- A data-publish PR should also build the web image (`build web (linux/arm64)`) before `latest` moves: release 2 once shipped with an image that still read catalogue.json from git.
- In Antigravity VMs, `gh release upload` hits `uploads.github.com` HTTP 401 through the VM proxy; publish data releases via `gh workflow run data-refresh.yml` instead (rule G-70), which also exercises the full CI release path.
- fueleconomy.gov: BEV range is column `range`; EPA kWh/100 mi never goes into the WLTP consumption field.

## Done (per task)
Acceptance criteria ticked · tests for every data rule and bug · local gate green, then CI green on the PR head · PR template filled with evidence · Status + Handoff notes in the task file · coverage report regenerated if the release changed · fresh review before merge.

## Finish the batch
State lives in task files and PRs, not here. When the batch is done or blocked: one line in `workstreams/WS0/INBOX.md` (`- YYYY-MM-DD HH:MM UTC · from <chat link> · …`, with the four retro answers or a link to them in a PR body), then stop. No STATUS or HANDOFF files.

## Open lane threads (from the retired WS1 HANDOFF/STATUS, 2026-11-18; WS0 turns them into tasks)
- After the first night run since #110: check refresh.json `images` (fetched / failed / stopped, `pending_generations` once #134 is in).
- Ioniq 5 facelift: RDW variant codes F5E62 etc. land on facelift-base (WS3 T-140 item 2); overlaps T-073 (#127).
- Press photos only when WS3 marks a maker `allowed` in `data/images/press-terms.yaml` (none today).
- #110 nit: COMMONS_LICENCE accepts any 2-letter CC port; needs the real CC 2.0–3.0 port list from creativecommons.org.
- #58 follow-up test for the `ac_kw_optional` rows guard.
- 🟡 #135 rebuild: Leaf e+ winter range went up (225 → 239) while EPA went down (364 → 346): not traced.
- Blocked: T-063 data side, T-064 part 2, EV3/Inster rows (Q-047), launch gate (Q-059).
