# T-164 Cite power for the rows that lose version flags only for missing power
Role: builder   Lane: data/seed, data/manual (WS3)   Wave: launch
Status: doing (batch: catalogue T-164, 2026-11-26)

## Goal
The rows Decision 088 can't compare only because `power_kw` is missing get a cited maker power, so their newest / older flags come back, and `renault-twingo-gen3-22kwh` gets its cited 22 kW AC figure.

## Acceptance criteria
- [ ] Re-run the list on `main` post-T-163: cite `power_kw` for the 20 rows from T-161's 22 that still lack `cited.power_kw` (Tesla first, 12 rows: Model 3 LR / LR 2021 / Performance / Performance 2021 / SR+ / SR+ LFP, Model S facelift 100D / 75D / P100D, Model S gen1 85 / 85D-90D, Model Y RWD; plus Mach-E ER AWD / SR RWD, Enyaq 80x RS, ID.3 Pro, e-tron GE S, Spring 65, EV3 AWD, EV6 84 AWD; note `volkswagen-id7-gen1-gtx` is AWD-only and `opel-mokka-gen1-54kwh` hits the Stellantis float bug handled in T-166).
- [ ] **Twingo 22 kW AC (T-163 WS3 ask):** cite `ac_kw: 22` for `renault-twingo-gen3-22kwh` from Renault's official Twingo press release / spec sheet so `guard_mixups` keeps 22 kW AC next to its cited 22 kWh battery instead of falling back to `kilowatt-openev`'s wrong 11 kW.
- [ ] Cite each from a maker-hosted document on `data/sources.yaml` (`maker-docs.cited_hosts` for `data/seed/variants.yaml` `cited:` blocks; `manual.cited_hosts` for `data/manual/` facts; Decision 087; flag any new official maker host in `data/sources.yaml` as a cross-lane WS1 edit); approvals for moved scores in their own gate PR (G-54).
- [ ] `sh data/seed/data_qa.sh`, `ev verify --base-release-from origin/main`, and plain `ev verify` (against release 3, which measures approvals): show flag-less row count before / after.

## Inputs
WS0 INBOX 2026-11-19 15:05 UTC (batch: data T-161, WS3 ask) & 2026-11-26 23:06 UTC (batch: data T-163 follow-up b + T-161 count); T-161 Handoff notes (the 22 rows).

## Out of scope
Code changes (T-163 / T-166).

## Handoff notes

## Review
