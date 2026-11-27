# T-167 Build and publish data release 4 (`data-v4`; `latest = 4`)
Role: builder   Lane: pipeline/, data/releases/ (WS1)   Wave: launch
Status: review · batch: T-167 (2026-11-27)

## Goal
Publish **data release 4** (`data-v4`, `data/releases/latest = 4`) containing every launch data & catalogue improvement since release 3 (T-149–T-166: photo bundle `images.tar`, `generations[].popularity`, `dc_speed_is_claim`, 128+ cited `maker-docs` facts, 419 variants, EV9/Model X/Stellantis fixes), with green CI, web e2e, and staging deploy — unblocking **T-157** (WS2).

## Acceptance criteria
- [x] **Trace pre-existing staging drift vs release 3 (62 lines):** investigate `mg-mg4-gen1-xpower` (61 lines: missing RDW 2024 `price_new.NL` + 60 derived `used_prices` bands) and `skoda-enyaq-gen1-80x` (1 line: `48.0 -> 47.9`) observed across T-163/T-164/T-166. Fix if it is a pipeline/matching regression, or document the upstream RDW change and add `release: 4` approvals in a separate gate-only PR (`config/approved_changes.yaml`, G-54) first.
- [x] **Fresh staging & clean release 4 build:** fetch release 3 locally (`uv run ev release fetch latest --via-gh` in proxy-routed VMs, G-66), refresh open sources (`ev refresh --force --no-release`; split slow sources like `rdw-defects` / `eea` across commands if needed to avoid a 10-min timeout; note if `discodata.eea.europa.eu` is down and whether cached EEA staging is used), and build release 4.
- [x] **QA & release invariants green:**
  - `ev verify` vs release 3 passes (`release_diff_blocking: 0`, `seed_mismatches: 0` [G-48], `missing_input_flag_changes: 0` [G-62] — *note: 10 report-only G-62 changes vs pre-Decision-088 release 3; 0 vs `origin/main`; see Handoff notes*).
  - `sh data/seed/data_qa.sh` (`pytest -m seed`, `backtest_rules.py`, `ev images check`, `ev release approvals`) passes.
  - `uv run python -m ev_pipeline.qa check-release ../data/releases/4` passes.
  - Confirm release 4 ships `images.tar` bundle (Decision 086 / T-150; total GitHub Release asset count well under the 450-asset guard), `generations[].popularity` (T-149), `dc_speed_is_claim` (T-163), and CC BY open-data bundle excludes `maker-docs` / photos.
- [x] **Publish `data-v4` & open `Data release 4` PR:** upload release 4 assets to GitHub Release `data-v4` via `pipeline/scripts/gh-publish-release.sh data/releases/4` (resumable, verified against `manifest.json` size + sha256) and open the PR with the 7 `in_git` files (`data/releases/4/{README.md,coverage.md,diff.json,manifest.json,qa.json,qa.md,retired_ids.json}`), `data/releases/latest` = `4`, and task Status/Handoff notes. Never commit files excluded by `.gitignore`.
- [ ] **End-to-end verification:** CI green on exact PR head (including `web` Playwright e2e reading `data-v4`, `pipeline`, `data-qa`, `repo-checks`, `ci-ok`), independent fresh review (`REVIEW.md` R0–R4, D1, D4) PASS, `sh scripts/merge_ready.sh <PR>` READY standalone, merged, and `Data publish` + `Images` staging deploy checked green on `main`.

## Inputs
- `workstreams/WS0/HANDOFF.md` & `INBOX.md` (T-149–T-166 merged; release-4 approvals #177, #184, #189, #190, #194, #196, #198, #203, #212, #213, #218, #219, #224)
- PR #169 (`Data release 3`) & PR #162 (`pipeline/scripts/gh-publish-release.sh`)
- Decisions 035, 044, 068, 086, 087, 088; rules G-34, G-48, G-54, G-62, G-66

## Out of scope
- New catalogue seed additions (remaining `no-variant` groups like `kia-ev5`, `bmw-ix3-gen2` wait for a post-release-4 pass)
- Web app changes to read `generations[].popularity` / unpack `images.tar` / show DC claim badge (**T-157**, starts right after release 4 lands)

## Handoff notes
- **Gate-only PR #224 (merged `a1355a2`, fresh review PASS `2394c0d`, branch deleted):** traced the 62 pre-existing RDW staging drift lines vs release 3 (`pipeline/ev_pipeline/sources/rdw/adapter.py` unchanged since 2026-11-15 `87cea7f`) and confirmed both are upstream RDW `m9d7-ebf2` fleet changes between 2026-11-18 and 2026-11-27:
  - `mg-mg4-gen1-xpower` (61 lines): live RDW has only 2 plates matching `___7%` for 2024 `SEH3|1EAB4EI` (38 total, 22 flagged `export_indicator='Ja'`), below `MIN_SAMPLE = 5`, so `price_new.NL.amount` (`41640 EUR`) is emitted without WLTP/power evidence and left unplaced by the attach-only matcher, clearing its 60 derived `used_prices.json` bands (4 sample bands remain: 3 NL Marktplaats + 1 BE 2dehands).
  - `skoda-enyaq-gen1-80x` (1 line): 2022 `ENYAQ 80X` `___7%` sample grew `n=7 -> n=8` (used imports), shifting medians `486 km / 18.07 -> 481 km / 18.17 kWh/100km` and nudging `scores.daily-driver+kerbside.urban.score` `48.0 -> 47.9` (`consider -> fallback`).
- **EEA fallback PR #225 (merged `97908b8`, fresh review PASS `5194d4b`, branch deleted):** `discodata.eea.europa.eu` returned HTTP 502 (and `sdi.eea.europa.eu` timed out, same as the 23 Nov scheduled `Data refresh` run `45180800593`), and in this Antigravity VM `gh release upload` to `uploads.github.com` returned `HTTP 401: Bad credentials` (GitHub plugin proxy only exchanges credentials for `api.github.com` / `github.com`). PR #225 added an optional `restore_from_release` hook on the `eea` adapter so ephemeral GitHub Actions runners (`data-refresh.yml`) reconstruct the 5,029 cached 2026-11-18 yearly EEA records from release 3's verified `facts.parquet` (preserving exact `retrieved_at: 2026-11-18` provenance and honest `status: failed`) instead of skipping the release.
- **Published `data-v4` via `Data refresh` run `45942519214` (PR #226):**
  - All 15 live open sources succeeded (`openev`, `kilowatt-openev`, `wikidata`, `fueleconomy`, `kba-fz10`, `ademe`, `dft-veh`, `eafo`, `bnetza`, `dft-charging`, `rdw`, `rdw-tgk`, `rdw-defects`, `geonames`, `meteostat`), `eea` honestly reported `failed` and restored 5,029 cached 2026-11-18 records from release 3, and `fetch_images` fetched all 120 photos + 115 Wikimedia licence templates (0 failures).
  - `gh-publish-release.sh data/releases/4 --replace-unmerged` published **290** assets to GitHub Release `data-v4` (`isDraft: false`, well under the 450-asset guard; down from 640 in release 3).
- **Release 4 invariants verified directly on fetched `data-v4` (`ev release fetch 4 --via-gh` -> `284 downloaded, 6 already ok, 1 unpacked`; `ev release verify 4` -> `ok`):**
  - `uv run python -m ev_pipeline.qa check-release ../data/releases/4`: **pass** (`provenance`: 9,957 values / 0 problems; `licence_gate`: 15 sources, 70,176 facts / 0 problems; `images`: 119 photos ok; `release_diff`: 0 blocking, 1,262 approved, 19,489 review; `0` impossible values vs 2 in release 3).
  - `ev verify --skip-tests` vs release 3: **pass** (`release_diff_blocking: 0`, `release_diff_approved: 1262`, `release_diff_retired: 21`, `release_diff_review: 19489`, `seed_mismatches: 0`, `variants: 419` vs `375` [+50 / -6, all 6 redirected in `retired_ids.json`]).
  - Note on G-62 (`missing_input_flag_changes: 10` report-only vs release 3): T-164/T-166 saw `0` vs `origin/main` (which already had Decision 088), whereas release 3 pre-dates Decision 088. The 10 report-only rows vs release 3 are 7 rows missing `power_kw` on a sibling (`audi-e-tron-ge-55` [4], `mercedes-eqa-h243-300-350-4matic` [2], `kia-ev6-gen1-gt` [1]) and 3 rows missing `dc_km_per_20min` (`hyundai-ioniq-5-facelift-63kwh-rwd` [1], `tesla-model-s-facelift-raven-long-range` [2, withheld by T-111 plausibility gate]). Flagged for WS3 post-release-4 cleanup.
  - `images.tar`: 29,296,640 bytes, 357 WebP files across 119 generations; `generations[].popularity` on **156** generations (Spearman 0.952, median rank move 4.0); `dc_speed_is_claim: true` on **4** rows (`ford-e-tourneo-courier-gen1-46kwh`, `hyundai-ioniq-5-facelift-awd`, `hyundai-ioniq-5-facelift-base`, `skoda-elroq-gen1-85`); **150** cited `maker-docs` facts + **174** `manual` facts; CC BY `open/` bundle (419 rows across 11 open sources) excludes `maker-docs`, `manual`, and photos.

## Review

