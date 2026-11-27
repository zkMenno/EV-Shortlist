# T-164 Cite power for the rows that lose version flags only for missing power
Role: builder   Lane: data/seed, data/manual (WS3)   Wave: launch
Status: done (batch: catalogue T-164, 2026-11-26; gate PR #218 merged b9317c0, data PR #220)

## Goal
The rows Decision 088 can't compare only because `power_kw` is missing get a cited maker power, so their newest / older flags come back, and `renault-twingo-gen3-22kwh` gets its cited 22 kW AC figure.

## Acceptance criteria
- [x] Re-run the list on `main` post-T-163: cite `power_kw` for the 20 rows from T-161's 22 that still lack `cited.power_kw` (Tesla first, 12 rows: Model 3 LR / LR 2021 / Performance / Performance 2021 / SR+ / SR+ LFP, Model S facelift 100D / 75D / P100D, Model S gen1 85 / 85D-90D, Model Y RWD; plus Mach-E ER AWD / SR RWD, Enyaq 80x RS, ID.3 Pro, e-tron GE S, Spring 65, EV3 AWD, EV6 84 AWD; note `volkswagen-id7-gen1-gtx` is AWD-only and `opel-mokka-gen1-54kwh` hits the Stellantis float bug handled in T-166).
- [x] **Twingo 22 kW AC (T-163 WS3 ask):** cite `ac_kw: 22` for `renault-twingo-gen3-22kwh` from Renault's official Twingo press release / spec sheet so `guard_mixups` keeps 22 kW AC next to its cited 22 kWh battery instead of falling back to `kilowatt-openev`'s wrong 11 kW.
- [x] Cite each from a maker-hosted document on `data/sources.yaml` (`maker-docs.cited_hosts` for `data/seed/variants.yaml` `cited:` blocks; `manual.cited_hosts` for `data/manual/` facts; Decision 087; flag any new official maker host in `data/sources.yaml` as a cross-lane WS1 edit); approvals for moved scores in their own gate PR (G-54).
- [x] `sh data/seed/data_qa.sh`, `ev verify --base-release-from origin/main`, and plain `ev verify` (against release 3, which measures approvals): show flag-less row count before / after.

## Inputs
WS0 INBOX 2026-11-19 15:05 UTC (batch: data T-161, WS3 ask) & 2026-11-26 23:06 UTC (batch: data T-163 follow-up b + T-161 count); T-161 Handoff notes (the 22 rows).

## Out of scope
Code changes (T-163 / T-166).

## Handoff notes
- **21 `power_kw` citations added in `data/seed/variants.yaml`** (all 20 remaining flag-less rows from T-161's 22, plus `tesla-model-s-facelift-raven-long-range` 415 kW to clear G-62):
  - **Tesla Model 3 (6) & Model Y (1):** cited from Tesla UK Support WLTP table (`https://www.tesla.com/en_gb/support/power-consumption`, matching OpenEV's Front+Rear kW convention): Model 3 SR+ / SR+ LFP `208` kW, LR / LR 2021 `366` kW (`158 F + 208 R`), Performance / Performance 2021 `393` kW (`158 F + 235 R`), Model Y RWD `220` kW.
  - **Tesla Model S (5 + Raven LR):** Model S 85 RWD `270` kW (`362 hp × 0.7457` from US EPA 2013 Test Car List `13tstcar.csv`, Public Domain 17 U.S.C. 105); Model S 85D/90D, 75D, 100D `386` kW (`193 F + 193 R`) and P90D/P100D `568` kW (`193 F + 375 R`) from Tesla, Inc.'s 2017 MY EPA/CARB Application for Certification (`dis.epa.gov` `docid=39834`, Engine Family `HTSLV00.0L2S`, maker document under Decisions 068/087); Model S Raven LR `415` kW (`205 F + 210 R`, ECE R85) from Tesla's 2012–2020 Model S Owner's Manual (`www.tesla.com/ownersmanual/2012_2020_models/en_kr/GUID-E414862C-CFA1-4A0B-9548-BE21C32CAA58.html`). Adding Raven LR cleared the G-62 warning where 2016–2019 75D/100D had falsely taken `newest-version` ahead of the un-powered 2019–2021 Raven (`missing_input_flag_changes: 2 -> 0`).
  - **Non-Tesla (8):** Ford Mustang Mach-E ER AWD `258` kW and SR RWD `198` kW (`www.fordpers.be` EU tech specs PDF); Škoda Enyaq 80x / RS `195` kW (`cdn.skoda-storyboard.com` `TD-ENYAQ-iV-en.pdf`); VW ID.3 Pro `150` kW (`www.volkswagen-newsroom.com` press release 6275); Audi e-tron S `370` kW boost (`www.audi.com` Audi Media Center A207063); Dacia Spring 2024 facelift 65 `48` kW (`cdn.group.renault.com` NL Aug 2025 price list PDF); Kia EV3 AWD `195` kW (`press.kia.com` DE MY27 press release PDF); Kia EV6 facelift 84 kWh AWD `239` kW (`press.kia.com` DE MJ25 press kit PDF).
- **Twingo 22 kW AC (T-163 WS3 ask):** cited `ac_kw: 22` on `renault-twingo-gen3-22kwh` from Renault Nederland's official April 2022 Twingo E-Tech Electric price list (`cdn.group.renault.com`, p. 16: `"Vermogen lader AC (kW/h) min-max 2,3 - 22 kW"`). Built row moves `ac_kw: 11 -> 22`, `ac_km_per_h: 67.9 -> 135.8`.
- **Cross-lane WS1 edit flagged (`data/sources.yaml`):** added 4 verified official hosts to `maker-docs.cited_hosts`: `www.tesla.com` (official Tesla WLTP support & Owner's Manual), `www.audi.com` (already vetted in `manual.cited_hosts`), `dis.epa.gov` (Tesla maker certification filings hosted on EPA DIS, Decisions 068/087), and `www.epa.gov` (US EPA Public Domain 17 U.S.C. 105 Test Car List, same agency as active `fueleconomy`). `apps/web/src/config/sources.generated.json` is unaffected (only `name/owner/licence/status/url/attribution` are emitted by `sources.mjs`).
- **Gate-only PR (G-54):** PR #218 (merged `b9317c0`) added `release: 4` approvals in `config/approved_changes.yaml` for the 3 variants with expected threshold-crossing diffs: `renault-twingo-gen3-22kwh` (`ac_kw: 11 -> 22`), `tesla-model-y-gen1-rwd` (`wltp_range_km: 430 -> 455`, also fills NL price `44,290 EUR`), and `skoda-enyaq-gen1-80x-rs` (power gate rightly rejects the mis-attached 250 kW 2026 `ENYAQ RS` RDW record `58,080 EUR`, clearing its NL price & 51 derived `used_prices.json` bands and cleaning consumption `16.9 -> 16.0` / WLTP `518 -> 527`, moving 4 road-tripper bands `fallback -> consider`).
- **Flag-less row counts (before → after on 2026-11-26 staging, `origin/main @ b9317c0` vs branch):**
  - T-161's 22 rows missing `power_kw`: **20 → 0**; T-161's 22 rows carrying `newest-version` / `older-version`: **0 → 13** (the remaining 7 now have honest cited power and stay flag-less on their own trim line or middle year span under Decision 088).
  - Overall catalogue rows missing `power_kw` in models with ≥2 same-drivetrain rows: **39 → 19** (the 20 target rows + Model S Raven LR minus AWD-only EV3 AWD).
  - Overall catalogue rows with `newest-version` / `older-version` flags: **88 → 108** (+20 net flagged rows).
- **Verification:** `sh data/seed/data_qa.sh` pass (`250 passed`, back-test `25/30` 83% / `30/30` within one band); `ev verify --base-release-from origin/main` pass (`release_diff_blocking: 0`, `release_diff_approved: 477`, `missing_input_flag_changes: 0`, `seed_mismatches: 0`; full `pytest` 1,956/1,956 pass once release 2 is present locally); plain `ev verify` vs release 3 has **0 T-164 blocking lines** (62 pre-existing RDW staging drift lines on `mg-mg4-gen1-xpower` and `skoda-enyaq-gen1-80x`).

## Review
- **Gate PR #218** (Fresh Reviewer subagent, 2026-11-26, head `215ca9b`): `R0–R3: pass` (`R4, D1–D13: n/a`), 0 must-fix / 0 should-fix / 0 nits.
- **Data PR #220** (Fresh Reviewer subagent, 2026-11-26, head `a3ce37c`): `R0–R3, D1, D2, D4: pass` (`R4: n/a`), 0 must-fix / 0 should-fix / 2 nits (Nit 1 `dis.epa.gov` wording fixed after merging `origin/main @ 386e93a`; Nit 2 cross-lane flag included in WS0 INBOX).


