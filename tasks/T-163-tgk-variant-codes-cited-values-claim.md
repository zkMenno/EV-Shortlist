# T-163 TGK variant codes as split evidence, cited power / gross reach the release, DC claim flag
Role: builder   Lane: pipeline/ (WS1)   Wave: launch
Status: doing (batch: data T-163, 2026-11-26)

## Goal
Tesla versions split by their type-approval variant code, cited maker power and gross values actually publish (Decision 068 / 087), and maker-claim DC figures are marked.

## Acceptance criteria
- [ ] **TGK variant code as split evidence** (T-160 WS1 ask): `tgk_split.yaml` can use the TGK variant code where pack kWh is missing: Tesla Model S `75R` vs `75D`; Model X `60X` / `75X` / `90X` / `100X` (rows from T-162). Fix the stale ~line 95 comment ("EV6 F5E12 unseeded"). Repro (G-51): tie / several counts for Model S / X before / after.
- [ ] **Cited power / gross reach the release:** T-160 reports cited `power_kw` and gross values never publish ("until Q-008"), e.g. Elroq 85 and the new T-160 rows show `power_kw` empty. Q-008 is answered (Decision 068, widened by 087): find the gate that still withholds them and let cited maker facts publish with their provenance. Show the rows that gain `power_kw`, and how many of T-161's 22 flag-less rows get their flag back.
- [ ] **`dc_speed_is_claim`** (schema field added by WS0, 2026-11-19): `derive/rows.py` `_charging` sets it from the minutes fact's `claim` (rows today: Ioniq 5 facelift base / AWD). Moved here from T-161. Also carry it into the open dataset: `pipeline/ev_pipeline/opendata/bundle.py` column + `COMPANION_OF` entry, as for `dc_peak_kw_is_claim`.
- [ ] Same-data rebuild diff (G-43), `ev verify --base-release-from origin/main` (code diff) and plain `ev verify` (against the latest release, for approvals) in the PR body, approvals in their own gate PR (G-54); tests with fixtures.

## Inputs
WS0 INBOX 2026-11-19 14:25 (schema ask), 15:05 (T-161), 16:05 (T-160) UTC; Q-008, Decision 068, 087; T-160, T-161 Handoff notes.

## Out of scope
New seed rows (T-162), power citations (T-164), verify / merge tools (T-165).

## Handoff notes

## Review
