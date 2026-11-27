"""T-166: Kia EV9 gen1 GT vs AWD / RWD TGK split (T-162 WS1 ask b, rule G-67).

Fixture `fixtures/rdw_tgk/split_t166_ev9.jsonl`: 8 real rdw-tgk staging records (CC0, RDW Open
Data, staging 2026-11-27) covering all 7 EV9 variant codes (`F7E42`, `F7E12`, `F6E34`, `F7E24`,
`F7E34`, `F6E54`, `F7E54`). Matched against the real seed and real `match/tgk_split.yaml`; each
case also runs with an empty table to prove the split is what decides.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ev_pipeline.match.matcher import TGK_MISFIT, TGK_TIE, match_records
from ev_pipeline.match.seed import load_manual_variants, load_seed
from ev_pipeline.merge.merge import merge_variant_facts
from ev_pipeline.merge.policy import load_policies
from ev_pipeline.records import SourceRecord

pytestmark = pytest.mark.seed

REPO = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures" / "rdw_tgk" / "split_t166_ev9.jsonl"
RECS = [SourceRecord.model_validate(json.loads(x)) for x in FIXTURE.read_text().splitlines()]


def _rec(code: str, year: int) -> SourceRecord:
    for r in RECS:
        if f"|{code}|" in r.record_key and r.year == year:
            return r
    raise LookupError((code, year))


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


@pytest.mark.parametrize(
    ("code", "year", "want", "before_target"),
    [
        ("F7E42", 2026, "kia-ev9-gen1-76kwh-rwd", "kia-ev9-gen1-76kwh-rwd"),
        ("F7E12", 2026, "kia-ev9-gen1-99kwh-rwd", "kia-ev9-gen1-gt"),
        ("F7E12", 2024, "kia-ev9-gen1-99kwh-rwd", TGK_TIE),
        ("F6E34", 2026, "kia-ev9-gen1-99kwh-awd", "kia-ev9-gen1-gt"),
        ("F7E24", 2026, "kia-ev9-gen1-99kwh-awd", "kia-ev9-gen1-gt"),
        ("F7E34", 2026, "kia-ev9-gen1-99kwh-awd", "kia-ev9-gen1-gt"),
        ("F6E54", 2025, "kia-ev9-gen1-gt", "kia-ev9-gen1-gt"),
        ("F7E54", 2026, "kia-ev9-gen1-gt", "kia-ev9-gen1-gt"),
    ],
)
def test_ev9_tgk_codes_split_cleanly(
    seed, code: str, year: int, want: str, before_target: str
) -> None:
    rec = _rec(code, year)
    before = _where(seed, rec, table={})
    if before_target == TGK_TIE:
        assert TGK_TIE in before
    else:
        assert before == before_target
    assert _where(seed, rec) == want


def test_ev9_gt_and_awd_merge_clean_wltp_and_top_speed(seed) -> None:
    """After splitting F6E54/F7E54 from 2025+ AWD/RWD, GT merges vmax=220 and WLTP 518 km
    without mixing 200 km/h AWD or 579 km RWD versions into GT."""
    s, manual = seed
    policies = load_policies(REPO / "data" / "field_sources.yaml")
    res = match_records(RECS, s, manual)
    by_v: dict[str, list] = {}
    for mf in res.spec_facts:
        if mf.source_id == "rdw-tgk":
            by_v.setdefault(mf.fact.subject_id.root, []).append(mf)

    gt = merge_variant_facts(by_v["kia-ev9-gen1-gt"], policies)
    awd = merge_variant_facts(by_v["kia-ev9-gen1-99kwh-awd"], policies)
    rwd = merge_variant_facts(by_v["kia-ev9-gen1-99kwh-rwd"], policies)

    assert gt["wltp_range_km"].value == 518.0
    assert gt["top_speed_kmh"].value == 220.0
    assert gt["consumption_kwh_100km"].value == 20.8
    assert awd["wltp_range_km"].value == 522.0
    assert awd["top_speed_kmh"].value == 200.0
    assert rwd["wltp_range_km"].value == 579.0
    assert rwd["top_speed_kmh"].value == 185.0


def test_unknown_ev9_code_goes_to_review(seed) -> None:
    unknown = _rec("F6E54", 2025).model_copy(
        update={"record_key": _rec("F6E54", 2025).record_key.replace("|F6E54|", "|F9E99|")}
    )
    why = _where(seed, unknown)
    assert why.startswith("attach-only: " + TGK_MISFIT) and "type_codes" in why
