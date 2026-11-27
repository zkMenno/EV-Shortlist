# Release QA, release 4

Overall: **review** (fail = blocked; review = published, items to check). Details in qa.json.

| Check | Blocking | Status | Summary |
|---|---|---|---|
| Provenance completeness | yes | pass | 9957 values checked; 0 problem(s) |
| Licence gate re-check | yes | pass | 15 sources, 70176 facts; 0 problem(s) |
| Diff vs previous release | no | flag | vs release 3: 375 -> 419 variants, +50 / -6; 6 flag(s) |
| Outliers and impossible values | no | flag | 0 impossible value(s), 162 outside P1-P99 (reference: release 3) |
| Coverage of the top-40 used models | no | info | 40 models; 2+ agreeing sources on every headline field: 0 (0%, target 80% before launch) |
| New sections (T-059) | no | flag | EPA 179 rows (0 with a 2nd EPA source via fueleconomy); years 10/12 generations corroborated; known issues 232 cohorts; charging stats 3810 rows |
| Plausibility gate (A-35 B4) | no | flag | 5 issue(s) withheld from the rows (in conflicts.csv), 38 to review |
| Car photos: licence, file-page template, credit, stored files (Decisions 081, 083) | yes | pass | 119 photo(s) ok |
| Release diff vs previous release (T-123) | yes | pass | vs release 3: 0 blocking, 1262 approved, 19489 review |
| Back-test (real range) | no | skipped | no real condition-tagged tests from licence-cleared sources yet (the measured-test sources are still waiting for permission); harness tested on fixtures only |

## Plausibility (first 10 each)

- withheld: byd-atto-3-gen1-60kwh: WLTP 510 km / 60.5 kWh = 8.43 km/kWh > 8 (withheld above 8.2 for body suv)
- withheld: hyundai-kona-electric-sx2-long-range: WLTP 484 km / 58 kWh = 8.34 km/kWh > 8 (withheld above 8.2 for body suv)
- withheld: hyundai-kona-electric-sx2-standard-range: WLTP 305 km / 36.5 kWh = 8.36 km/kWh > 8 (withheld above 8.2 for body suv)
- withheld: skoda-enyaq-gen1-85: WLTP 752 km / 77 kWh = 9.77 km/kWh > 8 (withheld above 8.2 for body suv)
- withheld: tesla-model-s-facelift-raven-long-range: dc_km_per_20min 167.6 = 1.47x the generation + pack median 113.7 (3 variants) > 1.3x
- review: bmw-i3-i01-120ah: WLTP 310 km / 37.9 kWh = 8.18 km/kWh > 8
- review: bmw-i3-i01-i3s-94ah: WLTP 245 km / 27.2 kWh = 9.01 km/kWh > 8
- review: byd-sealion-7-gen1-excellence-awd: dc_km_per_20min 181.5 = 1.39x the generation median 130.3 (3 variants) > 1.3x
- review: citroen-e-c3-gen1-electric-200: WLTP 232 km / 26 kWh = 8.92 km/kWh > 8
- review: citroen-e-c4-c41-54kwh: WLTP 418 km / 50.8 kWh = 8.23 km/kWh > 8
- review: dacia-spring-gen1-essential: WLTP 230 km / 26.8 kWh = 8.58 km/kWh > 8
- review: dacia-spring-gen1-essential-comfort: WLTP 230 km / 26.8 kWh = 8.58 km/kWh > 8
- review: dacia-spring-gen1-essential-extreme: WLTP 230 km / 26.8 kWh = 8.58 km/kWh > 8
- review: fiat-500e-332-24kwh: WLTP 190 km / 21.3 kWh = 8.92 km/kWh > 8
- review: fiat-500e-332-42kwh: WLTP 337 km / 37.3 kWh = 9.03 km/kWh > 8

## Diff flags

- dc_peak_kw: filled share fell 7.8 points
- dc_avg_10_80_kw: filled share fell 5.6 points
- accel_0_100_s: filled share fell 7.2 points
- weight_kg: filled share fell 7.5 points
- dc_minutes_10_80: filled share fell 5.6 points
- dc_peak_held_min: filled share fell 6.4 points

## Profile fields (winter range, real range, DC km in 20 min)

Report only. Ratios compare the catalogue figure with the calibrated consumption matrix (1.0 = same). The winter temperature step is unvalidated (needs winter road tests, Q-059).

- **Winter range** (matrix, t1): 375 of 419 variants; 20 °C consumption out of sample: 7.0 % median abs error (n 176); the temperature step is not validated.
- **Real range** (catalogue): 380 variants; vs EPA: 7.18 % median abs error (n 104); vs matrix mild range: median 1.106 (P10 1.02, P90 1.207), 204 of 375 differ by more than 10 %.
- **DC km in 20 min** (catalogue): 342 variants; curves default 276, estimated 60, None 6; its motorway consumption vs the matrix: median 0.956 (P10 0.922, P90 1.053), 49 of 338 differ by more than 10 %. No licence-clean charging test yet.
- **WLTP consumption**: 381 variants; EPA in sample 6.47 % median abs error (n 176), out of sample 7.0 % median abs error (n 176); our estimate (net kWh / WLTP x charging losses) vs official WLTP: 3.0 % median abs error (n 257).

## Popularity back-test (T-155, report only)

Spearman 0.952 over 87 generations; median rank move 4.0; top 10 overlap 9/10, top 20 16/20.

## Release diff 3 -> 4 (T-123)

Status **pass**: 0 blocking, 1262 approved, 21 retired, 19489 review. Full list: `data/review/release_diff.csv`.

| file | added | changed | charging | cleared | file_removed | filled | removed | source_lost |
|---|---|---|---|---|---|---|---|---|
| catalogue.json:generations |  | 1 |  |  |  | 1018 |  |  |
| catalogue.json:rows | 50 | 498 |  | 2042 |  | 2154 | 6 |  |
| charging_stats.json:series |  |  | 16 |  |  |  |  |  |
| consumption_matrix.json:variants | 50 | 522 |  | 2 |  | 1 | 5 |  |
| shortlist_scores.json:variants | 50 | 1182 |  | 2 |  | 30 | 6 |  |
| towns/fr.json:towns |  | 2 |  |  |  |  |  |  |
| used_prices.json:variants | 30 | 7723 |  | 836 |  | 4540 | 6 |  |

Biggest moves:
- shortlist_scores.json audi-e-tron-ge-s scores.road-tripper+kerbside.rural.score: 0 -> 5.1 (new)
- shortlist_scores.json audi-e-tron-ge-s scores.road-tripper.rural.score: 0 -> 5.6 (new)
- shortlist_scores.json porsche-taycan-gen1-base factors.road-tripper.efficiency: 0.034 -> 0.138 (+305.9 %)
- shortlist_scores.json nissan-leaf-ze1-e-plus-62kwh factors.road-tripper.efficiency: 0.138 -> 0.332 (+140.6 %)
- shortlist_scores.json mg-mg4-gen1-xpower factors.road-tripper.efficiency: 0.104 -> 0.225 (+116.3 %)
- shortlist_scores.json ford-e-tourneo-courier-gen1-base factors.daily-driver.winter-range: 0.184 -> 0 (-100.0 %)
- shortlist_scores.json ford-e-tourneo-courier-gen1-base scores.daily-driver+kerbside.rural.score: 41.2 -> 0 (-100.0 %)
- shortlist_scores.json ford-e-tourneo-courier-gen1-base scores.daily-driver.rural.score: 45.8 -> 0 (-100.0 %)
- catalogue.json vinfast-vf6-gen1-base registered_count_nl: 471 -> 783 (+66.2 %)
- catalogue.json vinfast-vf6-gen1-eco registered_count_nl: 471 -> 783 (+66.2 %)

Stale approvals (matched nothing): 14
