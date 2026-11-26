# T-165 Tools round 2: seed-pinned tests in data_qa, missing-input flag report, merge_ready stuck checks, CI runs approvals
Role: builder   Lane: pipeline/ (WS1); cross-lane, flag them: `data/seed/data_qa.sh` (WS3), `scripts/merge_ready.*` (WS0), `.github/workflows/ci.yml` and `pipeline/pyproject.toml` (gate files: their own PR)   Wave: launch
Status: doing (batch: T-165, 2026-11-26)

## Goal
The misses the 19 Nov afternoon batches hit by hand get checked by a tool.

## Acceptance criteria
- [x] **G-61:** `data_qa.sh` runs the tests that pin seed state (`pytest -m seed`; register the `seed` marker in `pipeline/pyproject.toml` (gate PR #210); mark `tests/test_t153_split.py`, `tests/test_t159_split.py` and any other seed-pinned test), so a seed change can't break them unseen until CI.
- [x] **G-62:** `ev verify` lists rows whose derived flags change only because an input is missing (e.g. `power_kw` → Decision 088 "unknown → no flag"), with the input named.
- [x] **G-63:** `merge_ready.sh` treats a check run with a `conclusion` and `completed_at` as completed even if its `status` still says `in_progress`, and says so in its output.
- [x] **CI data-qa** runs `ev release approvals` (gate PR #210, ci.yml only).
- [x] Tests with fixtures (no network).

## Inputs
WS0 INBOX 2026-11-19 15:05, 15:06, 16:05 UTC (retros); rules G-61–G-63.

## Out of scope
Matching and data (T-163).

## Handoff notes
- **Gate-only PR (#210):** split per G-06 / REVIEW D11. Registered `seed` pytest marker in `pipeline/pyproject.toml` and added `fetch-depth: 0` + `Check approved_changes.yaml (G-57, G-54)` (`uv run ev release approvals --base "$base"`) to `.github/workflows/ci.yml` `data-qa`.
- **G-61 (`data/seed/data_qa.sh` + `pipeline/tests/`):** marked pure-seed modules (`test_t153_split.py`, `test_t159_split.py`, `test_t144_seed_guards.py`, `test_t136d_coverage_gems.py`, `test_seed_t051.py`) with `pytestmark = pytest.mark.seed` and real-seed tests in 9 mixed modules (`test_match.py`, `test_registrations.py`, `test_shared_year_source_names.py`, `test_seed_cited.py`, `test_qa_top40.py`, `test_a06_fixes.py`, `test_pack_guard.py`, `test_source_wikidata.py`, `test_t134_images.py`) with `@pytest.mark.seed` (201 tests, ~25 s, zero release-asset dependency). `data/seed/data_qa.sh` now runs `uv run pytest -m seed -q`.
- **G-62 (`pipeline/ev_pipeline/verify/run.py`, `pipeline/.claude/skills/verify/SKILL.md`):** `rebuild()` returns `shortlist` (`res.shortlist`, on both pass and `ReleaseError`); `verify()` loads `old_scores` (from `base_dir` for `--base-release-from` or `scratch/releases/<latest>/shortlist_scores.json`), runs `missing_input_flag_changes()`, records `rep.sections["missing_input_flags"]` + `rep.numbers["missing_input_flag_changes"]`, and renders `## Derived flag changes from missing inputs (G-62)` (report-only). Covers `newest-version`, `older-version` (Decision 088: `year_start`, `drivetrain`, `power_kw`, `dc_km_per_20min`, including peer missing-input cascades and excluding rows that wouldn't earn the flag even with the missing input or that became `ruled-out`), `lfp-daily-100` (`charge_100_daily`), and `too-big-for-b-roads` (`width_mm`, `kerb_mass_kg`). Dry run on release 3 vs Decision 088: 30 items (all missing `power_kw` / peer `power_kw` / `dc_km_per_20min`), 0 false positives on true trim-line splits.
- **G-63 (`scripts/merge_ready.py`, `scripts/merge_ready.sh`, `scripts/tests/test_merge_ready.py`):** `gather()` keeps `completed_at`; `evaluate()` treats any non-`completed` check run with both non-empty `conclusion` and `completed_at` as completed, emits a G-63 `note:` line, and still enforces `conclusion in OK_CONCLUSIONS`.
- **Cross-lane edits (COORDINATOR-approved in brief):** `data/seed/data_qa.sh` (WS3), `scripts/merge_ready.*` + `scripts/tests/test_merge_ready.py` (WS0), plus gate-only PR #210 (`pipeline/pyproject.toml`, `.github/workflows/ci.yml`).
- **Tests:** `pipeline/tests/test_t165_verify_merge_tools.py` (13 tests, fixture-only, no network) and `scripts/tests/test_merge_ready.py` (4 new G-63 tests + `completed_at` gather assertion; 29 total in `scripts/tests`).

## Review
