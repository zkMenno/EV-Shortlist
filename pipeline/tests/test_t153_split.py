"""T-153: split evidence for TGK versions of variants that share a pack.

Fixture `fixtures/rdw_tgk/split_t153.jsonl`: 8 real rdw-tgk staging records (CC0, RDW Open
Data, fetched 2026-11-19): Peugeot 208 ZKXZ (2021, 2023, 2025) and ZKWZ (2024), Tesla
Model Y Y5LD at 217 and 250 km/h and Y5CD (2021), VW ID.4 Pro 150 kW. Matched against the
real seed (data/seed) and the real split table (match/tgk_split.yaml); each case is also run
with an empty table to show the rule is what decides.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from ev_pipeline.match.matcher import (
    TGK_MISFIT,
    TGK_SPLIT_FILE,
    TGK_TIE,
    load_tgk_split,
    match_records,
    tgk_type_codes,
)
from ev_pipeline.match.seed import load_manual_variants, load_seed
from ev_pipeline.records import SourceRecord
from ev_pipeline.schema_models import FactField

pytestmark = pytest.mark.seed

REPO = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures" / "rdw_tgk" / "split_t153.jsonl"
RECS = [SourceRecord.model_validate(json.loads(x)) for x in FIXTURE.read_text().splitlines()]


def _rec(code: str, year: int, top_speed: float | None = None) -> SourceRecord:
    for r in RECS:
        ts = r.specs.get(FactField.top_speed_kmh)
        speed_ok = top_speed is None or (ts is not None and ts.value == top_speed)
        if f"|{code}" in r.record_key and r.year == year and speed_ok:
            return r
    raise LookupError(code)


@pytest.fixture(scope="module")
def seed():
    s = load_seed(REPO / "data" / "seed" / "models.yaml")
    manual, _ = load_manual_variants(REPO / "data" / "seed" / "variants.yaml")
    return s, manual


def _where(seed, rec: SourceRecord, table: dict | None = None) -> str:
    s, manual = seed
    res = match_records([rec], s, manual, tgk_split=table)
    placed = {
        mf.fact.subject_id.root
        for mf in res.spec_facts
        if mf.source_id == "rdw-tgk" and mf.fact.source_record == rec.record_key
    }
    if placed:
        [vid] = placed
        return vid
    [why] = [u.reason for u in res.unmatched if u.record_key == rec.record_key]
    return why


BUILT_ONLY = {
    "tesla-model-y-gen1-long-range-rwd",
    # T-159: OpenEV-built rows (no seed row) whose TGK versions needed split evidence.
    "hyundai-ioniq-5-facelift-n",
    "porsche-taycan-gen1-base",
    "porsche-taycan-gen1-4s",
    "porsche-taycan-gen1-turbo",
    "porsche-taycan-gen1-turbo-s",
    "porsche-taycan-gen1-turbo-gt",
}
E208, MY, ID4 = "peugeot-e-208-p21", "tesla-model-y-gen1", "volkswagen-id4-gen1"


def test_30min_power_and_type_code_split_the_stellantis_pair(seed) -> None:
    tied = _rec("ZKXZ-J0J000", 2023)  # 57 kW 30-min, WLTP 362: both packs fit the energy
    assert TGK_TIE in _where(seed, tied, {})
    assert _where(seed, tied) == f"{E208}-50kwh"
    assert _where(seed, _rec("ZKWZ-K0V000", 2024)) == f"{E208}-51kwh"
    assert _where(seed, _rec("ZKXZ-J0A000", 2021)) == f"{E208}-50kwh"


def test_a_version_no_row_fits_goes_to_review(seed) -> None:
    """2025 ZKXZ (57 kW) on the T-153 seed: the 50 kWh row ended 2023 (+1), the 51 kWh row is
    ZKWZ / 62 kW. Before T-153 the year put it on the 51 kWh row; with the split it is a misfit
    for review. T-160 opened the 50 kWh row's end year, so the old seed is rebuilt here."""
    s, manual = seed
    old = [replace(v, year_end=2023) if v.id == f"{E208}-50kwh" else v for v in manual]
    late = _rec("ZKXZ-K0L000", 2025)
    assert _where((s, old), late, {}) == f"{E208}-51kwh"
    why = _where((s, old), late)
    assert why.startswith(f"attach-only: {TGK_MISFIT} the type_codes (H/ZKXZ)")


def test_t160_late_zkxz_lands_on_the_open_50kwh_row(seed) -> None:
    """T-160: Stellantis kept the 100 kW / 50 kWh e-208 on sale after the 2023 facelift, so
    the seed row runs on and the 2025 ZKXZ (57 kW) version places on it by the split."""
    late = _rec("ZKXZ-K0L000", 2025)
    assert _where(seed, late) == f"{E208}-50kwh"


def test_top_speed_splits_model_y_long_range_and_performance(seed) -> None:
    lr, perf, lr21 = _rec("Y5LD", 2024, 217), _rec("Y5LD", 2022, 250), _rec("Y5CD", 2021)
    assert _where(seed, lr) == f"{MY}-long-range"
    assert _where(seed, perf) == f"{MY}-performance"
    assert _where(seed, lr21) == f"{MY}-long-range"  # was placed on Performance
    assert _where(seed, lr21, {}) != f"{MY}-long-range"


def test_motors_rule_splits_id4_pro_from_gtx(seed) -> None:
    pro = _rec("4ACEBJAL1FX2", 2022)  # states 70 kW 30-min: one drivetrain row
    assert TGK_TIE in _where(seed, pro, {})
    assert _where(seed, pro) == f"{ID4}-pro"


def test_motors_rule_only_rules_out_listed_variants(seed) -> None:
    """A-05 F12: some dual-motor versions carry one 30-min row (I-Pace), so the rule is
    opt-in per variant; without `motors: 2` on the GTX the tie stays."""
    pro = _rec("4ACEBJAL1FX2", 2022)
    table = {k: v for k, v in load_tgk_split().items() if k != f"{ID4}-gtx"}
    assert TGK_TIE in _where(seed, pro, table)


def test_type_codes_from_the_record_key() -> None:
    assert tgk_type_codes(_rec("ZKWZ-K0V000", 2024)) == {"H", "ZKWZ"}
    assert tgk_type_codes(_rec("Y5CD", 2021)) == {"Y5CD", "BZB3S5T3"}
    bad = RECS[0].model_copy(update={"record_key": "openev:x"})
    assert tgk_type_codes(bad) == set()


def test_table_rows_are_valid_and_point_at_seed_generations(tmp_path: Path) -> None:
    table = load_tgk_split()
    gens = set(load_seed(REPO / "data" / "seed" / "models.yaml").generations)
    manual, _ = load_manual_variants(REPO / "data" / "seed" / "variants.yaml")
    seed_ids = {mv.id for mv in manual}
    for vid in table:
        assert any(vid.startswith(f"{g}-") for g in gens), vid
        # a typo'd id would silently do nothing: every row is a seed variant or a known
        # source-built row (OpenEV's Model Y Long Range RWD has no seed row)
        assert vid in seed_ids or vid in BUILT_ONLY, vid
    bad = tmp_path / "t.yaml"
    bad.write_text("schema: tgk-split/v1\nvariants:\n  x: {power_30min_kw: [57]}\n")
    with pytest.raises(ValueError, match="basis"):
        load_tgk_split(bad)
    bad.write_text("schema: tgk-split/v1\nvariants:\n  x: {motors: 3, basis: b}\n")
    with pytest.raises(ValueError, match="motors"):
        load_tgk_split(bad)
    bad.write_text("schema: other\n")
    with pytest.raises(ValueError, match="schema"):
        load_tgk_split(bad)
    assert TGK_SPLIT_FILE.name == "tgk_split.yaml"
