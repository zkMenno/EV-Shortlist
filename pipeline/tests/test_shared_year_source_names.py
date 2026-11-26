"""Shared model year + year-scoped `source_names` (PR #91 review, Ioniq 5).

T-068 split the Ioniq 5 into gen1 [2021, 2024] and facelift [2024, -]. T-110 had pinned OpenEV
"Base" / "AWD" up to MY2024 to the gen1 77.4 kWh seed rows (`source_names` with years). In the
shared year 2024 the matcher still chose the facelift (name evidence on both, newest wins), so
MY2024 records made facelift rows with gen1 figures. A seed source name that covers the
record's model year now picks its generation first.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from ev_pipeline.match.matcher import match_records
from ev_pipeline.match.seed import parse_manual_variants, parse_seed
from ev_pipeline.records import SourceRecord, SpecValue

OPENEV = {"id": "openev", "name": "Open EV Data", "licence": "CDLA-Permissive-2.0"}
G1, FL = "hyundai-ioniq-5-gen1", "hyundai-ioniq-5-facelift"
SEED = {
    "makes": [
        {
            "id": "hyundai",
            "name": "Hyundai",
            "models": [
                {
                    "id": "hyundai-ioniq-5",
                    "name": "Ioniq 5",
                    "generations": [
                        {"id": G1, "years": [2021, 2024]},
                        {"id": FL, "years": [2024, None]},
                    ],
                }
            ],
        }
    ]
}


def _manual() -> Any:
    v = {
        "generation_id": G1,
        "id": f"{G1}-77kwh-rwd",
        "name": "77.4 kWh RWD",
        "years": [2022, 2024],
        "source_names": {"openev": [{"name": "Base", "years": [None, 2024]}]},
        "specs": {"battery_kwh_net": 77.4, "power_kw": 168},
    }
    mv, problems = parse_manual_variants({"variants": [v]}, date(2026, 11, 17))
    assert problems == []
    return mv


def _rec(year: int, kwh: float) -> SourceRecord:
    return SourceRecord(
        source=OPENEV,
        record_key=f"openev:ioniq_5/{year}/base",
        kind="spec",
        make="Hyundai",
        model="Ioniq 5",
        variant_name="Base",
        year=year,
        specs={
            "battery_kwh_net": SpecValue(value=kwh, unit="kWh"),
            "power_kw": SpecValue(value=168, unit="kW"),
        },  # fmt: skip
        retrieved_at=date(2026, 11, 17),
        confidence="medium",
    )


def _placed(res: Any) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for mf in res.spec_facts:
        if mf.fact.source.id.root == "openev":
            out.setdefault(str(mf.fact.subject_id.root), set()).add(str(mf.fact.source_record))
    return out


def test_scoped_source_name_picks_the_generation_in_a_shared_year() -> None:
    seed = parse_seed(SEED)
    res = match_records([_rec(2023, 77.4), _rec(2024, 77.4), _rec(2025, 77.4)], seed, _manual())
    placed = _placed(res)
    assert placed[f"{G1}-77kwh-rwd"] == {"openev:ioniq_5/2023/base", "openev:ioniq_5/2024/base"}
    # MY2025 is outside the name's years: the facelift, as before.
    assert placed[f"{FL}-base"] == {"openev:ioniq_5/2025/base"}


@pytest.mark.seed
def test_shipped_seed_pins_ioniq5_my2024_base_and_awd_to_gen1() -> None:
    """The real seed: OpenEV MY2024 "Base" / "AWD" land on the gen1 77.4 kWh rows."""
    from pathlib import Path

    from ev_pipeline.match.matcher import build_evidence, find_generation
    from ev_pipeline.match.seed import load_manual_variants, load_seed

    repo = Path(__file__).resolve().parents[2]
    seed = load_seed(repo / "data" / "seed" / "models.yaml")
    manual, _ = load_manual_variants(repo / "data" / "seed" / "variants.yaml")
    recs = [_rec(2024, 72.6), _rec(2025, 72.6)]
    recs.append(recs[0].model_copy(update={"variant_name": "AWD", "record_key": "awd/2024"}))
    ev = build_evidence(recs, seed, manual)
    model = seed.models["hyundai-ioniq-5"]
    assert find_generation(model, 2024, ev, recs[0])[0].id == G1
    assert find_generation(model, 2024, ev, recs[2])[0].id == G1
    assert find_generation(model, 2025, ev, recs[1])[0].id == FL


@pytest.mark.seed
def test_retired_ioniq5_release1_ids_have_live_successors() -> None:
    """Release 1 ids hyundai-ioniq-5-gen1-{awd,base,n} must redirect, not 410 (T-062)."""
    from pathlib import Path

    from ev_pipeline.release.retired import compute_retired, load_hand_kept

    repo = Path(__file__).resolve().parents[2]
    hand = load_hand_kept(repo / "data" / "seed")
    old = {f"{G1}-awd", f"{G1}-base", f"{G1}-n"}
    live = {f"{G1}-77kwh-awd", f"{G1}-77kwh-rwd", f"{FL}-n"}
    prev = {"rows": [{"variant_id": v} for v in old]}
    res = compute_retired(prev, None, live, hand)
    # Only the Ioniq 5 ids: retired_ids.yaml also holds other makes' successors (T-148).
    got = {k: v for k, v in res.ids.items() if k in old}
    assert got == {f"{G1}-awd": f"{G1}-77kwh-awd", f"{G1}-base": f"{G1}-77kwh-rwd",
                   f"{G1}-n": f"{FL}-n"}  # fmt: skip
