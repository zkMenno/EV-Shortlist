# T-167 Build and publish data release 4 (`data-v4`; `latest = 4`)
Role: builder   Lane: pipeline/, data/releases/ (WS1)   Wave: launch
Status: todo

## Goal
Publish **data release 4** (`data-v4`, `data/releases/latest = 4`) containing every launch data & catalogue improvement since release 3 (T-149–T-166: photo bundle `images.tar`, `generations[].popularity`, `dc_speed_is_claim`, 128+ cited `maker-docs` facts, 419 variants, EV9/Model X/Stellantis fixes), with green CI, web e2e, and staging deploy — unblocking **T-157** (WS2).

## Acceptance criteria
- [ ] **Trace pre-existing staging drift vs release 3 (62 lines):** investigate `mg-mg4-gen1-xpower` (61 lines: missing RDW 2024 `price_new.NL` + 60 derived `used_prices` bands) and `skoda-enyaq-gen1-80x` (1 line: `48.0 -> 47.9`) observed across T-163/T-164/T-166. Fix if it is a pipeline/matching regression, or document the upstream RDW change and add `release: 4` approvals in a separate gate-only PR (`config/approved_changes.yaml`, G-54) first.
- [ ] **Fresh staging & clean release 4 build:** fetch release 3 locally (`uv run ev release fetch latest --via-gh` in proxy-routed VMs, G-66), refresh open sources (`ev refresh --force --no-release`; split slow sources like `rdw-defects` / `eea` across commands if needed to avoid a 10-min timeout; note if `discodata.eea.europa.eu` is down and whether cached EEA staging is used), and build release 4.
- [ ] **QA & release invariants green:**
  - `ev verify` vs release 3 passes (`release_diff_blocking: 0`, `seed_mismatches: 0` [G-48], `missing_input_flag_changes: 0` [G-62]).
  - `sh data/seed/data_qa.sh` (`pytest -m seed`, `backtest_rules.py`, `ev images check`, `ev release approvals`) passes.
  - `uv run python -m ev_pipeline.qa check-release ../data/releases/4` passes.
  - Confirm release 4 ships `images.tar` bundle (Decision 086 / T-150; total GitHub Release asset count well under the 450-asset guard), `generations[].popularity` (T-149), `dc_speed_is_claim` (T-163), and CC BY open-data bundle excludes `maker-docs` / photos.
- [ ] **Publish `data-v4` & open `Data release 4` PR:** upload release 4 assets to GitHub Release `data-v4` via `pipeline/scripts/gh-publish-release.sh data/releases/4` (resumable, verified against `manifest.json` size + sha256) and open the PR with the 7 `in_git` files (`data/releases/4/{README.md,coverage.md,diff.json,manifest.json,qa.json,qa.md,retired_ids.json}`), `data/releases/latest` = `4`, and task Status/Handoff notes. Never commit files excluded by `.gitignore`.
- [ ] **End-to-end verification:** CI green on exact PR head (including `web` Playwright e2e reading `data-v4`, `pipeline`, `data-qa`, `repo-checks`, `ci-ok`), independent fresh review (`REVIEW.md` R0–R4, D1, D4) PASS, `sh scripts/merge_ready.sh <PR>` READY standalone, merged, and `Data publish` + `Images` staging deploy checked green on `main`.

## Inputs
- `workstreams/WS0/HANDOFF.md` & `INBOX.md` (T-149–T-166 merged; release-4 approvals #177, #184, #189, #190, #194, #196, #198, #203, #212, #213, #218, #219)
- PR #169 (`Data release 3`) & PR #162 (`pipeline/scripts/gh-publish-release.sh`)
- Decisions 035, 044, 068, 086, 087, 088; rules G-34, G-48, G-54, G-62, G-66

## Out of scope
- New catalogue seed additions (remaining `no-variant` groups like `kia-ev5`, `bmw-ix3-gen2` wait for a post-release-4 pass)
- Web app changes to read `generations[].popularity` / unpack `images.tar` / show DC claim badge (**T-157**, starts right after release 4 lands)

## Handoff notes

## Review
