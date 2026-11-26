"""T-159: motor-count ties and other trims' TGK versions, decided by match/tgk_split.yaml.

Fixture `fixtures/rdw_tgk/split_t159.jsonl`: 15 real rdw-tgk staging records (CC0, RDW Open
Data, staging recorded 2026-11-19) plus the OpenEV rows (CDLA-Permissive-2.0) of the Ioniq 5
facelift and Taycan MY2023-25, which build the Ioniq 5 N and Taycan rows. Matched against the
real seed and the real split table; each case also runs with an empty table, which shows the
table is what decides (the "before" of the T-159 brief).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ev_pipeline.match.matcher import TGK_MISFIT, TGK_TIE, match_records
from ev_pipeline.match.seed import load_manual_variants, load_seed
from ev_pipeline.records import SourceRecord

pytestmark = pytest.mark.seed

REPO = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures" / "rdw_tgk" / "split_t159.jsonl"
RECS = [SourceRecord.model_validate(json.loads(x)) for x in FIXTURE.read_text().splitlines()]
TGK = [r for r in RECS if r.source.id.root == "rdw-tgk"]
OPENEV = [r for r in RECS if r.source.id.root == "openev"]


def _tgk(code: str, year: int, model: str = "") -> SourceRecord:
    for r in TGK:
        if code in r.record_key and r.year == year and model in (r.model or "").upper():
            return r
    raise LookupError(code)


@pytest.fixture(scope="module")
def seed():
    s = load_seed(REPO / "data" / "seed" / "models.yaml")
    manual, _ = load_manual_variants(REPO / "data" / "seed" / "variants.yaml")
    return s, manual


def _where(seed, rec: SourceRecord, table: dict | None = None) -> str:
    s, manual = seed
    res = match_records([*OPENEV, rec], s, manual, tgk_split=table)
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


@pytest.mark.parametrize(
    ("code", "year", "want", "model"),
    [
        ("|F5E22|", 2026, "kia-ev3-gen1-long-range", "EV3"),  # one motor, 30-min 50 kW
        ("|F5E34|", 2026, "kia-ev3-gen1-awd", "EV3"),  # two motors
        ("|F5E22|E11A11", 2025, "kia-ev6-facelift-84kwh-rwd", "EV6"),
        ("|F5E44|E11B11", 2025, "kia-ev6-facelift-84kwh-awd", ""),
        ("|41GA", 2025, "mini-countryman-e-gen1-e", ""),  # 170 km/h, 30-min 68 kW
        ("|F4E12|E11AZ1", 2025, "hyundai-inster-gen1-42kwh", ""),  # 30-min 23.7 kW
    ],
)
def test_motor_count_ties_resolve(seed, code, year, want, model):
    rec = _tgk(code, year, model)
    assert _where(seed, rec) == want
    # Before T-159 (no split rows): the same version tied between the two trims.
    assert TGK_TIE in _where(seed, rec, table={})


def test_unchanged_placements_stay(seed):
    # Already placed before (SE ALL4 by name, Inster 49 by name); the table agrees.
    assert _where(seed, _tgk("|51GA", 2025)) == "mini-countryman-e-gen1-se-all4"
    assert _where(seed, _tgk("|F4E22|E11BZ1", 2025)) == "hyundai-inster-gen1-49kwh"


def test_ev6_facelift_gt_goes_to_review(seed):
    # F5E64 is the EV6 GT (260 km/h), not seeded: its type code fits neither 84 kWh row.
    why = _where(seed, _tgk("|F5E64|", 2025))
    assert why.startswith("attach-only: " + TGK_MISFIT) and "type_codes" in why


def test_ioniq5_facelift_versions_leave_the_n_row(seed):
    rec = _tgk("|F5E22|E11A11", 2025, "IONIQ")  # 84 kWh one motor, 570 km
    # Before: the trade-name list "IONIQ5 / IONIQ5 N" gave the name word "N" -> the N row.
    assert _where(seed, rec, table={}) == "hyundai-ioniq-5-facelift-n"
    assert _where(seed, rec) == "hyundai-ioniq-5-facelift-base"
    assert _where(seed, _tgk("|F5E74|", 2025)) == "hyundai-ioniq-5-facelift-n"


def test_q8_e_tron_versions_leave_the_e_tron_55(seed):
    q8 = _tgk("|XBM1JAQ1|", 2022)  # "Q8 55 E-TRON", 629 km, first admitted 2022
    assert _where(seed, q8, table={}) == "audi-e-tron-ge-55"
    why = _where(seed, q8)
    assert why.startswith("attach-only: " + TGK_MISFIT) and "type_codes" in why
    assert _where(seed, _tgk("|XBM1JQ1|", 2021)) == "audi-e-tron-ge-55"


def test_taycan_2024_versions_leave_the_pre_update_rows(seed):
    new = _tgk("|JN22|", 2024)  # 4S after the 2024 update, 676 km
    assert _where(seed, new, table={}) == "porsche-taycan-gen1-4s"
    why = _where(seed, new)
    assert why.startswith("attach-only: " + TGK_MISFIT) and "type_codes" in why
    assert _where(seed, _tgk("|JB22|1141000", 2022)) == "porsche-taycan-gen1-4s"


def test_taycan_rows_take_only_their_own_battery(seed):
    # The 4th digit of the uitvoering code is the pack (fresh review #199): x0x0000 =
    # Performance Battery (base row, 71 kWh net), x1x1000 = Performance Battery Plus (4S row).
    assert _where(seed, _tgk("|JA12|1040000", 2022)) == "porsche-taycan-gen1-base"
    big = _where(seed, _tgk("|JA12|1041000", 2022))  # 520 km, 102 kWh drawn
    assert big.startswith("attach-only: " + TGK_MISFIT) and "type_codes" in big
    small_4s = _where(seed, _tgk("|JB22|1050000", 2022))  # 429 km, 84.5 kWh drawn
    assert small_4s.startswith("attach-only: " + TGK_MISFIT) and "type_codes" in small_4s
