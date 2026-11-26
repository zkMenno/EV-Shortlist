# T-159 Matching follow-ups: motor-count ties, other trims' TGK versions, year-only splits
Role: builder   Lane: pipeline/ (WS1)   Wave: launch
Status: done (#198 gate, #199 part 1, #203 gate, #204 part 2; merged 2026-11-19 by batch: data T-159)

## Goal
TGK versions land on the right trim: ties split by motor count, other trims' versions stop landing on a row, and rows that differ only by year get their per-year RDW records.

## Acceptance criteria
- [x] **Ties by motor count / drivetrain** (T-154 ask): extend `pipeline/ev_pipeline/match/tgk_split.yaml` so these resolve, or stay tied with a reason: Kia EV3 LR vs AWD, EV6 facelift RWD vs AWD, MINI Countryman E vs SE ALL4, Hyundai Inster 42 vs 49. Repro (G-51): tie count for the four before / after on the current seed.
- [x] **Other trims' versions** (T-155 ask 2, now held by T-155's guard): Ioniq 5 N gets 530–570 km versions, e-tron 55 gets Q8 e-tron 629 km, Inster 49 a 42 kWh 293 km version, Taycan gen1 facelift 665–676 km versions. Fix the matching so they land on their own trim (or no row); the guard's held count drops.
- [x] **Year-only splits** (T-156 ask): an RDW per-year record is placed by year when only years separate two rows (e.g. the 2026 e-Tourneo Courier record, unplaced now).
- [x] **Model Y gen1 Performance:** its 507 km WLTP comes from the RDW 2021 aggregate (T-153 Handoff notes); place or drop that value so the Performance row shows its own figure.
- [x] **Fingerprint** (T-153 follow-up 6): `ev variants propose` counts a group as `have` when every version is on its right row, so Model Y / e-208 / Corsa leave `several`. Only if time allows; else leave it in Handoff notes.
- [x] Split into two PRs if large (ties + other trims / year splits + Model Y + fingerprint). Same-data rebuild diff (G-43), queue numbers before / after (tie, several, have), `ev verify --base main` in the PR body; tests with fixtures.

## Inputs
WS0 INBOX 2026-11-19 09:15 (batch: catalogue T-154, ask 1), 10:38 (batch: data T-155, ask 2), 10:45 (batch: catalogue T-156, WS1 ask), 10:54 (batch: data T-153, WS1 follow-ups); T-153 and T-155 Handoff notes.

## Out of scope
The Elroq alias (T-160, WS3). Version-rule change (T-161). `ev verify` tools (T-158).

## Handoff notes
**Batch: data T-159 (2026-11-19).** Part 1 = gate #198 + #199 (merged); part 2 = gate #203 + data PR. Staging recorded 2026-11-19 12:53 UTC for every number.
- **Split evidence (part 1)**, `match/tgk_split.yaml`: EV3 (F5E12 / F5E22 / F5E34+F5E44), EV6 facelift (F5E22 / F5E44; F5E64 = GT → review), Countryman (170 / 180 km/h), Inster (30-min 23.7 / 28.2 kW), Ioniq 5 facelift (N = F5E74 only: the trade-name list "IONIQ5 / IONIQ5 N" on every version gave the word "N" to the N row), e-tron GE 50 / 55 / S codes (2022 "Q8 55" versions → review), Taycan (2020-23 codes; base and 4S by pack too: type code pairs `JA12+1040000`, new in `_split_fits`; uitvoering 4th digit 0 = PB, 1 = PB+). Same staging main → #199: 14 rows changed, T-155 guard held facts 1231 → 1182, queue tie 135 → 126, have 241 → 243.
- **Inster 49 "293 km"** (T-155 list) is an F4E22 / 28.2 kW version = the 49 kWh car: stays on the 49 row, held by the guard. Not a matching bug.
- **Model-year aggregates (part 2)**, `matcher.year_aggregate_pick`: an RDW `[merk|handelsbenaming|jaar]` aggregate whose only evidence is its own WLTP, with 2+ rows holding its year → review (29 aggregates on today's staging, e.g. Model Y 2021 507 km: Performance 507 → 514 from its own TGK versions). No evidence + rows split only by year → the one row holding the year (2026 E-Tourneo Courier NL price → `-46kwh`). 11 rows change (part 1 → part 2), 1 blocking (e-5008 band, #203). Tried first: year-only for every aggregate + no own numbers at all: 160 placements moved incl. wrong ones (Corsa / e-208 2024+ onto the 51 kWh rows while 50 kWh cars still sold): dropped.
- **Fingerprint (part 2)**, `variants/propose.split_by_evidence`: a group placed on 2+ variants that all have split evidence splits per variant; Model Y / e-208 / Corsa leave `several`. Queue part 1 → part 2: have 243 → 262, several 42 → 34, tie 126, no-fit 48 → 51 (unplaced members of split groups now show as their own groups, e.g. 11 e-208 ZKXZ 2025-26 versions = T-153 follow-up 1 for WS3).
- **Follow-ups (not done):** (1) Q8 e-tron rows hold each other's codes (XBM1JAQ1 on q8-50-sportback, XBMQ3AQ1 on q8-50): add Q8 codes to tgk_split. (2) EV6 gen1 77 kWh RWD / AWD / GT ties: same evidence as the facelift (F5E22 / F5E44 / F5E54), not added (scope). (3) Taycan 2020-21 versions go to review on year (rows start 2023, OpenEV model years); 2024-update Taycan and Taycan 4 / GTS have no rows (WS3). (4) Many T-155 guard holds are shipped WLTPs older than the row's versions (ID.4 Pro shipped 496 vs versions 575-650; Enyaq 85 shipped 752 vs 607-633): worth a look. (5) Ioniq 5 facelift base / AWD still one fingerprint group before part 2.

## Review
