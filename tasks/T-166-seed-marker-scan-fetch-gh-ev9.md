# T-166 Tools & fixes: seed-marker scan (G-65), `ev release fetch --via-gh` (G-66), Kia EV9 GT split, `trim_lines` float fix
Role: builder   Lane: pipeline/ (WS1)   Wave: launch
Status: done (Antigravity: batch T-166 2026-11-26; PR #219 gate, PR #221)

## Goal
Automate the seed-marker check so new real-seed tests can't skip `data_qa.sh`, make `ev release fetch` work cleanly inside proxy-routed VMs via `gh`, split Kia EV9 GT from AWD in `tgk_split.yaml`, and fix the IEEE-754 float boundary bug in `trim_lines` splitting Stellantis 100→115 kW pairs.

## Acceptance criteria
- [x] **G-65 (seed-marker scan test):** Add a fast fixture test under `pipeline/tests/` (e.g. `test_seed_marker_audit.py`) that scans `pipeline/tests/test_*.py` (AST or static scan) for references/reads of committed `data/seed/*.yaml` (including module-level path constants like `REAL_SEED` in `test_scoped_aliases.py`) and asserts every such test or module carries `@pytest.mark.seed`. Verify it catches an unmarked real-seed test in a synthetic test case and passes on all current tests.
- [x] **G-66 (`ev release fetch --via-gh`):** Add a `--via-gh` option (and/or clean fallback message) to `ev release fetch` that downloads release assets using `gh release download` and places them according to `manifest.json`, verifying every file's size and sha256 identically to the HTTP path (including `images.tar` if present). Unit tests with mocked subprocess + fixtures (no network).
- [x] **Kia EV9 GT `tgk_split.yaml` (T-162 WS1 ask b):** Split `kia-ev9-gen1` `F6E54` / `F7E54` (GT, `vmax=220`, WLTP 518 km) from 2025+ `F6E34` / `F7E24` / `F7E34` AWD (`vmax=200`) so `kia-ev9-gen1-gt` stops withholding WLTP. Follow G-67 (group staging records by `(variant, uitvoering, wltp_range_km)` first). Repro (G-51): before/after on `kia-ev9-gen1-gt` and `kia-ev9-gen1-99kwh-awd`.
- [x] **Stellantis `trim_lines` float bug (T-163 follow-up a):** Fix `pipeline/ev_pipeline/derive/shortlist.py:130` where IEEE-754 `100.0 * (1 + 0.15) == 114.99999999999999 < 115.0` splits all 5 Stellantis 100→115 kW pairs (e-C4, Corsa-e, Mokka, e-2008, e-208) by `1.4e-14` kW (use `low * (1 + gap) + 1e-9` or `math.isclose`). Unit test covering exact `100.0` vs `115.0` at `gap=0.15` + back-test (`backtest_rules.py`) passes.
- [x] Same-data rebuild diff (G-43), `ev verify --base-release-from origin/main` + plain `ev verify` (against release 3); any release-4 approvals in a separate gate-only PR (G-54). All unit tests, `ruff check`, `ruff format --check`, and `sh data/seed/data_qa.sh` green locally first (no live network calls in tests).

## Inputs
- WS0 INBOX `2026-11-26 21:18 UTC` (batch: T-165 retro proposal → G-65)
- WS0 INBOX `2026-11-26 22:00 UTC` (batch: catalogue T-162 WS1 ask b + retro proposal → G-66)
- WS0 INBOX `2026-11-26 23:06 UTC` (batch: data T-163 follow-up a: `derive/shortlist.py:130` `trim_lines` float bug)
- `docs/process/rules.md` rules G-61, G-65, G-66, G-67

## Out of scope
- Model X pre-Raven variant codes (shipped in T-163 #215)
- Remaining `no-variant` catalogue seed groups (`kia-ev5`, `bmw-ix3-gen2`, etc.)
- Building/publishing release 4 (separate release-4 batch after T-164 and T-166 merge)

## Handoff notes
- **Gate PR #219 merged (`386e93a`):** 1 `release: 4` approval in `config/approved_changes.yaml` for `kia-ev9-gen1-gt` `seats: 7 -> 6` (`Decision 049 (T-166 gate)`); fresh review PASS on `8967f40` (`R0–R3: pass`, 0 findings), `merge_ready.sh` READY.
- **Code PR #221 merged (`d5a231c`):** all 4 deliverables shipped; round-1 review caught 3 AST edge cases in `test_seed_marker_audit.py` (fixed in `22083d5`), merged `origin/main` (#220 T-164) in `c79a99b`, round-2 fresh review PASS on `c79a99b`, `merge_ready.sh` READY.
- **G-65 (`pipeline/tests/test_seed_marker_audit.py`):** AST scanner across `pipeline/tests/test_*.py` tracking `__file__`-rooted repo/data paths, multi-segment `/` literals, tuple unpacking (`MANUAL, _ = ...`), module-level constants (`REAL_SEED`, `SEED`), helper calls, fixtures, `load_links(REPO_DATA)`, `load_hand_kept(...)`, and class/module `pytestmark`; excludes non-YAML files (`validate_variants.py`, `data_qa.sh`) and `tmp_path`/fixture paths. Passes on all repo tests; synthetic tests + in-memory stripped `test_scoped_aliases.py` regression verify recall (17/17 real-seed modules caught when markers stripped).
- **G-66 (`pipeline/ev_pipeline/release/publish.py`, `commands/releases.py`, `tests/test_release_publish.py`):** Added `--via-gh` to `ev release fetch` using `gh release download` into a temp dir, verifying every asset's existence, size, and sha256 before placing atomically into `release_dir` and unpacking bundles (`images.tar`) identically to HTTP; added `FetchBlocked` catch with `--via-gh` retry hint. Dogfooded locally to fetch release 3 (640 assets) and release 2 (145 assets), both `ev release verify` ok; 5 mocked-subprocess unit tests added (no network).
- **Kia EV9 GT split (`pipeline/ev_pipeline/match/tgk_split.yaml`, `tests/test_t166_ev9_split.py`, `tests/fixtures/rdw_tgk/split_t166_ev9.jsonl`):** Grouped all 48 Kia EV9 `rdw-tgk` staging records by `(variant, uitvoering, wltp_range_km)` (G-67); split all 4 rows (`F7E42` 76 kWh RWD 185 km/h, `F7E12` 99.8 kWh RWD 185 km/h, `F6E34`/`F7E24`/`F7E34` 99.8 kWh AWD 200 km/h dual-motor, `F6E54`/`F7E54` GT 220 km/h dual-motor). Unmatched EV9 TGK ties `12 -> 0` (`48/48` placed, `+88` facts); `kia-ev9-gen1-gt` drops all 17 conflicting non-GT records (`wltp_range_km: 510 -> 518` with 0 conflicts, `consumption_kwh_100km: 22.0 -> 20.8`, `mass_running_order_kg: 2664 -> 2718`, `seats: 7 -> 6`).
- **Stellantis `trim_lines` float fix (`pipeline/ev_pipeline/derive/shortlist.py:133`, `tests/test_shortlist.py`):** Guarded `pw > limit` with `not math.isclose(pw, limit, rel_tol=1e-9, abs_tol=1e-9)`. All 5 Stellantis 100→115 kW pairs (`citroen-e-c4`, `opel-corsa-e`, `opel-mokka`, `peugeot-e-2008`, `peugeot-e-208`) now share one trim line; all 5 115 kW rows gain `bonus:newest-version` (+4 pts, 0 blocking). `backtest_rules.py`: 25/30 exact (83%), 30/30 within one band (100%).
- **Verification (post-T-164 `origin/main @ 4699bdc`):** `ruff check` + `ruff format --check` clean; `sh data/seed/data_qa.sh` pass (`260 passed, 1719 deselected`, 1,979 total pipeline tests, CI `pipeline` green on `c79a99b`); `ev verify --base-release-from origin/main` **pass** (`0 blocking, 1 approved, 67 review, 0 seed_mismatches, 0 missing_input_flag_changes, 419 variants`, facts `65,035 -> 65,123` [`+88`]); plain `ev verify` vs release 3 has **0** T-166 blocking lines (`860` approved, `62` pre-existing `origin/main` staging drift lines on `mg-mg4-gen1-xpower` [61] and `skoda-enyaq-gen1-80x` [1]).

## Review
- 2026-11-27 (fresh reviewer, gate PR #219): PASS on `8967f40` — `R0–R3: pass` (0 findings).
- 2026-11-27 (fresh reviewer, PR #221): round 1 CHANGES on `405ab3a` (1 must-fix `_flatten_div_chain` multi-segment reversal, 1 should-fix tuple unpacking, 2 nits) → fixed in `22083d5` + merged T-164 in `c79a99b` → round 2 PASS on `c79a99b` — `R0–R3, D1, D3, D4, D13: pass` (0 must-fix, 0 should-fix).


