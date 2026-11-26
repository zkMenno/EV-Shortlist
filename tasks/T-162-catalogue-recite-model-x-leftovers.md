# T-162 Re-cite MX-30 + EV6 63, Elroq 85 DC check, Model X gen1, Citigo e / Mii, EV9, Marvel R, Sealion 7
Role: builder   Lane: data/seed, data/manual (WS3)   Wave: launch
Status: doing (batch: catalogue T-162, 2026-11-26)

## Goal
T-160's two weak citations move to maker-hosted documents, the Elroq 85 DC peak is checked before launch, and the biggest no-variant groups left get cited rows.

## Acceptance criteria
- [x] **Re-cite to maker-hosted documents:** Mazda MX-30 (Mazda DE price list) and Kia EV6 63 kWh (press.kia.com kit) replace T-160's current citations; values change only if the maker document says otherwise (say which).
- [x] **Elroq 85 DC peak:** check the shipped 185 kW against a Škoda document; fix or confirm with the citation.
- [x] **Tesla Model X gen1:** rows per Tesla type-approval variant (60X / 75X / 90X / 100X …) as Tesla documents allow, cited WLTP per row. Records land on them once T-163 adds TGK variant codes as split evidence; if T-163 isn't merged, seed the rows and note the expected `tie` in Handoff notes.
- [x] **Then, biggest EU cars first:** Škoda Citigo e iV / SEAT Mii electric, Kia EV9, MG Marvel R, BYD Sealion 7. List what's left in Handoff notes.
- [x] Maker documents only, cited per car, never a whole table (Decision 087); built drivetrain and WLTP match the seed (G-48); `sh data/seed/data_qa.sh` (incl. the seed-pinned split tests once T-165 adds them, else run `pytest tests/test_t153_split.py tests/test_t159_split.py` by hand) and `ev verify --base-release-from origin/main` (code diff) plus plain `ev verify` (against the latest published release, which is what measures approvals) pass.
- [x] Queue numbers before / after (no-variant EU cars: 406,363 in 195 groups after T-160).

## Inputs
WS0 INBOX 2026-11-19 16:05 UTC (batch: catalogue T-160, "Left" + WS3 asks); T-160 Handoff notes; Decision 057, 068, 087.

## Out of scope
Power citations for the 22 flag-less rows (T-164). Matcher changes (T-163). `tgk_split.yaml` (WS1).

## Handoff notes
2026-11-26, batch: catalogue T-162. Staging recorded 2026-11-26 20:24–20:39 UTC (all non-EEA sources; `discodata.eea.europa.eu` returned HTTP 502 throughout the session, and `meteostat` / `rdw-defects` were not re-fetched). Gate-only PR #212 merged as `625c566` before this data PR.

- **Re-citations (no values changed):**
  - `mazda-mx-30-gen1-ev` (and pack `mazda-mx-30-35-5`): moved from password-walled `de.mazda-press.com` to Mazda DE's public price list `https://media-assets.mazda.eu/raw/upload/mazdade/globalassets/pdfs/brochure/mx-30/mazda-mx-30-preisliste-01feb2023.pdf` (p. 20: 35.5 kWh gross, 107 kW, WLTP 200 km, Vorderradantrieb / FWD). Values unchanged.
  - `kia-ev6-facelift-63kwh-rwd`: moved `power_kw: 125` and `wltp_range_km: 428` from dealer copy `widmann-winterholler.de` to Kia DE's official press kit `https://press.kia.com/content/dam/kiapress/DE/Germany/pressemappen/ev6/24_11/Kia_EV6_MJ25_Pressemappe_11-24.pdf` (p. 5 / p. 28 footnote `*`: 125 kW, 63 kWh, RWD, 428 km WLTP). Values unchanged.
- **Škoda Elroq 85 DC peak fix (`data/manual/specs/t162-catalogue-facts.yaml`, `data/sources.yaml`):**
  - OpenEV MY2025 Base carried `185 kW` (the Elroq RS figure); KilowattApp had `175 kW` (early launch / 85x). Both official Škoda Auto Elroq Technical Data sheets on `cdn.skoda-storyboard.com` (`TD-Elroq-en_f8cdb684.pdf`, 15 Dec 2025, p. 2; also `Skoda_Elroq_Technical_data_d5686460.pdf`, 5 May 2025) state **135 kW max DC / 28 min (10–80 %)** for Elroq 85 RWD (vs 175 kW / 28 min for 85x AWD and 185 kW / 26 min for RS).
  - Added `cdn.skoda-storyboard.com` to `data/sources.yaml` (`manual.cited_hosts`) and cited `dc_peak_kw: 135` + `dc_minutes_10_80: 28` (`claim: true`, `confidence: medium`) in `data/manual/specs/t162-catalogue-facts.yaml`.
  - Built row moves: `dc_peak_kw 185 -> 135`, `dc_minutes_10_80 25.9 -> 28`, `dc_avg_10_80_kw 124.7 -> 115.5`, `dc_km_per_20min 207.7 -> 192.3`, `dc_curve_status default -> ""`, `dc_peak_held_min 6 -> ""`, `scores.road-tripper.urban.band shortlist -> consider` (53.8 -> 51.4). All 4 blocking lines vs `origin/main` approved in gate PR #212 (`release: 4`); 0 blocking against published release 3 (where `skoda-elroq-gen1-85` is a new row).
- **17 new cited seed rows (`data/seed/variants.yaml`, `variant_links.yaml`, `battery_packs.yaml`, `platforms.yaml`, `t162-catalogue-facts.yaml`):**
  - `tesla-model-x-gen1` (6 rows): `60d` (`60D (60 kWh)`, 2016–17), `75d` (`75D / Standard Range (75 kWh)`, 2016–20, WLTP 375 km from `XA1`), `90d` (`90D / P90D (90 kWh)`, 2016–18), `100d` (`100D / P100D`, 2016–19, 100 kWh per `service.tesla.com`), `long-range` (`Long Range (Raven)`, 2019–21, 100 kWh + WLTP 507 km from `XA3 EB`), `performance` (`Performance (Raven)`, 2019–21, 100 kWh + WLTP 487 km from `XA3 EP`). Built: `75d` 72.5 net / 375 WLTP / 292.5 real; `long-range` 98 net / 507 WLTP / 395.5 real; `performance` 95 net / 487 WLTP / 379.9 real; `100d` 95 net / 406.3 real; `90d` 85.5 net / 351.4 real; `60d` 281.2 real. Also pulls 5,227 pre-2021 registrations off `tesla-model-x-palladium` (`6511 -> 1284`). **Expected `tie` (until T-163):** the 7 pre-Raven NEDC/none TGK groups (`60X`/`75X`/`90X`/`100X`/`P90X`/`P100X`, 3,531 NL cars) land in `tie` (0 `no-fit`) until T-163 adds TGK variant-code split evidence; `XA1` (75D) is `have` and `XA3` (`EB`/`EP`) is `several`.
  - `skoda-citigo-e-gen1-ev` (2020–21, FWD, 32.3 kWh net / 61 kW per `cdn.skoda-storyboard.com`; WLTP left to RDW like `e-up-gen1-32kwh`): built FWD, 32.3 net, WLTP 254 km, real 215.9 km, AC 7.2 kW. Queue: `have` (1,409 NL).
  - `seat-mii-electric-gen1-ev` (2020–22, FWD, 32.3 kWh net / 61 kW per `mundoseat.seat.com`; WLTP left to RDW): built FWD, 32.3 net, WLTP 251 km, real 213.3 km, AC 11 kW (upstream KilowattApp has two Mii files, 7.2 and 11 kW — minor pre-existing source quirk). Queue: `have` (2,022 NL).
  - `kia-ev9-gen1` (4 rows, new packs `egmp-76-1` and `egmp-99-8`): `76kwh-rwd` (2025+, 76.1 net, WLTP 443, real 354.4), `99kwh-rwd` (2023+, 96 net, WLTP 563, real 450.4), `99kwh-awd` (2023+, 95 net, WLTP 505, real 393.9), `gt` (2025+, 96 net, real 379.6, EPA 434.5; WLTP withheld by `guard_contradicted` because 2025 AWD `F6E34`/`F7E24`/`F7E34` 522 km versions currently attach to `gt` against Kia DE's cited 510 km — **WS1 split ask** below).
  - `mg-marvel-r-gen1` (2 rows, new platform `mg-marvel-r` and pack `mg-marvel-r-70`, cited `news.mgmotor.eu`): `rwd` (2021–24, WLTP 402, real 321.6), `performance-awd` (2021–24, WLTP 370, real 288.6).
  - `byd-sealion-7-gen1` (3 rows, new packs `byd-blade-82-5` and `byd-blade-91-3`, `charger_400v: native`, cited `byd.com/eu`): `comfort-rwd` (WLTP 482, real 385.6), `design-awd` (WLTP 456, real 355.7), `excellence-awd` (WLTP 502, real 391.6). Queue: 3/3 `have`.
- **WS1 asks (for T-163 / `tgk_split.yaml`):**
  1. `tesla-model-x-gen1`: TGK variant-code split for pre-Raven `60X` / `75X` / `90X` / `P90X` / `100X` / `P100X` (currently 7 expected `tie` groups, 3,531 NL cars).
  2. `kia-ev9-gen1`: TGK variant-code split separating `F6E54`/`F7E54` (GT, `vmax=220`, WLTP 518 km) from 2025+ `F6E34`/`F7E24`/`F7E34` (99.8 kWh AWD, `vmax=200`, WLTP 505–551 km) so `kia-ev9-gen1-gt` receives only GT versions and ships its 518 km WLTP cleanly.
- **Verification & queue numbers:**
  - `sh data/seed/data_qa.sh`: pass (`0 error(s), 182 warning(s)`, back-test 25/30 exact / 30/30 within 1 band, `approvals: ok`, 237 G-61 seed-pinned tests passed).
  - `ev manual check`: `15 files, 237 valid facts, 0 errors, 0 warnings`.
  - `pytest pipeline/tests/test_t153_split.py pipeline/tests/test_t159_split.py`: `20 passed`.
  - `ev verify --base-release-from origin/main` (code diff on same staging): **pass** (`variants: 402 -> 419`, `seed_mismatches: 0`, `missing_input_flag_changes: 0`, `release_diff_blocking: 0`, `release_diff_approved: 4`, `release_diff_review: 175`).
  - Plain `ev verify` (against published release 3): T-162 adds **0 blocking lines** against release 3 (all 10,322 blocking lines in local plain `ev verify` were missing `meteostat` towns (10,260) plus pre-existing `origin/main` staging drift on `mg-mg4-gen1-xpower` (61) and `skoda-enyaq-gen1-80x` (1), verified untouched by T-162).
  - Queue (`ev variants propose`, same 2026-11-26 staging; `eu_cars` could not be refreshed due to upstream `discodata.eea.europa.eu` HTTP 502): `groups_no_variant: 195 -> 174` (**-21 groups**, NL cars `58,140 -> 47,082`, **-11,058 NL cars**); `groups_have: 268 -> 278` (+10); `groups_several: 34 -> 38` (+4); `groups_tie: 126 -> 133` (+7, expected Model X gen1 ties); `groups_no_fit: 48 -> 48` (0 new no-fit); `candidate_groups: 243 -> 222` (-21).
- **What's left (biggest remaining `no-variant` groups by NL cars on 2026-11-26 staging):** `kia-ev5-gen1` (4,665 NL / 2 groups), `bmw-ix3-gen2` (3,368 / 2), `mg-mg5-gen1` (2,960 / 4), `opel-ampera-e-gen1` (2,622 / 2), `kia-ev4-gen1` (2,307 / 2), `opel-frontera-gen1` (2,027 / 2), `xpeng-g9-gen1` (1,822 / 3), `opel-astra-electric-gen1` (1,426 / 2), `citroen-e-c3-aircross-gen1` (1,410 / 2), `byd-seal-u-gen1` (1,404 / 2), `xpeng-g6-facelift` (1,404 / 4), `mazda-6e-gen1` (1,299 / 2), `byd-dolphin-surf-gen1` (1,044 / 3), `suzuki-e-vitara-gen1` (1,030 / 3), `mercedes-evito-tourer-gen1` (982 / 3), `renault-twingo-e-tech` (974 / 2), `peugeot-e-308-gen1` (967 / 2).

## Review
- PR #212 (gate-only, `config/approved_changes.yaml`): Fresh subagent reviewer, 2026-11-26, head `76395ce` then re-verified on merge head `bd5e6c2` — `R0–R3: pass; R4, D1–D13: n/a (bd5e6c2)` (0 findings; https://github.com/zkMenno/EV-Shortlist/pull/212#issuecomment-7203739820). Merged as `625c566` after `merge_ready.sh` READY.
