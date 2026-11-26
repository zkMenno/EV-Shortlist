# T-166 Tools & matching follow-ups: seed-marker scan (G-65), `ev release fetch --via-gh` (G-66), Kia EV9 GT split
Role: builder   Lane: pipeline/ (WS1)   Wave: launch
Status: todo

## Goal
Automate the seed-marker check so new real-seed tests can't skip `data_qa.sh`, make `ev release fetch` work cleanly inside proxy-routed VMs via `gh`, and split Kia EV9 GT from AWD in `tgk_split.yaml` so EV9 GT stops withholding WLTP.

## Acceptance criteria
- [ ] **G-65 (seed-marker scan test):** Add a fast fixture test under `pipeline/tests/` (e.g. `test_seed_marker_audit.py`) that scans `pipeline/tests/test_*.py` (AST or static scan) for references/reads of committed `data/seed/*.yaml` (including module-level path constants like `REAL_SEED` in `test_scoped_aliases.py`) and asserts every such test or module carries `@pytest.mark.seed`. Verify it catches an unmarked real-seed test in a synthetic test case and passes on all current tests.
- [ ] **G-66 (`ev release fetch --via-gh`):** Add a `--via-gh` option (and/or clean fallback message) to `ev release fetch` that downloads release assets using `gh release download` and places them according to `manifest.json`, verifying every file's size and sha256 identically to the HTTP path (including `images.tar` if present). Unit tests with mocked subprocess + fixtures (no network).
- [ ] **Kia EV9 GT `tgk_split.yaml` (T-162 WS1 ask b):** Split `kia-ev9-gen1` `F6E54` / `F7E54` (GT, `vmax=220`, WLTP 518 km) from 2025+ `F6E34` / `F7E24` / `F7E34` AWD (`vmax=200`) so `kia-ev9-gen1-gt` stops withholding WLTP. Repro (G-51): before/after on `kia-ev9-gen1-gt` and `kia-ev9-gen1-awd`, same-data rebuild diff (G-43), `ev verify --base-release-from origin/main` + plain `ev verify`; any release-4 approvals in a separate gate-only PR (G-54).
- [ ] All unit tests, `ruff check`, `ruff format --check`, and `sh data/seed/data_qa.sh` green locally first (no live network calls in tests).

## Inputs
- WS0 INBOX `2026-11-26 21:18 UTC` (batch: T-165 retro proposal → G-65)
- WS0 INBOX `2026-11-26 22:00 UTC` (batch: catalogue T-162 WS1 ask b + retro proposal → G-66)
- `docs/process/rules.md` rules G-61, G-65, G-66

## Out of scope
- Model X pre-Raven variant codes (handled in T-163 #215)
- Remaining `no-variant` catalogue seed groups (`kia-ev5`, `bmw-ix3-gen2`, etc.)
- Building/publishing release 4 (separate release-4 batch after T-163/T-164/T-166 merge)

## Handoff notes

## Review
